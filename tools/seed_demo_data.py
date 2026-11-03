#!/usr/bin/env python3
"""Fill the local storage/ranking databases with FAKE demo data so the web UI can be previewed.

The data is random: it does not reflect real malicious activity of these networks.
Keys and computations mirror bin/ranking.py and bgpranking/bgpranking.py.

    python tools/seed_demo_data.py            # 45 days of demo data
    python tools/seed_demo_data.py --clear    # remove it again
"""

import argparse
import random
from datetime import date, timedelta
from ipaddress import ip_network

from redis import Redis

from bgpranking.default import get_config, get_socket_path
from bgpranking.helpers import load_all_modules_configs

DAYS = 45
DEMO_TAG = 'demo-seed'

# asn: (description, address-space size (v4), v6 size, [v4 prefixes], [v6 prefixes], badness)
ASNS = {
    '64500': ('EXAMPLE-HOSTING-A, NL', 65536, 2**80, ['198.51.100.0/24', '203.0.113.0/24', '192.0.2.0/24'], ['2001:db8:100::/48'], 9.0),
    '64501': ('BULLETPROOF-NET, RU', 4096, 2**72, ['198.18.0.0/24', '198.18.1.0/24'], ['2001:db8:200::/48'], 14.0),
    '64502': ('CHEAP-VPS-CLOUD, US', 262144, 2**90, ['198.19.0.0/24', '198.19.8.0/24', '198.19.16.0/24'], ['2001:db8:300::/48', '2001:db8:301::/48'], 6.0),
    '64503': ('RESIDENTIAL-ISP-B, BR', 1048576, 2**96, ['100.64.0.0/22', '100.64.8.0/22'], ['2001:db8:400::/40'], 4.0),
    '64504': ('SMALL-DATACENTER, LU', 1024, 2**64, ['192.88.99.0/24'], ['2001:db8:500::/48'], 3.0),
    '64505': ('MOBILE-OPERATOR-C, IN', 2097152, 2**96, ['100.65.0.0/20'], ['2001:db8:6000::/36'], 2.5),
    '64506': ('UNIVERSITY-NET, DE', 131072, 2**80, ['100.66.0.0/22'], ['2001:db8:700::/48'], 1.2),
    '64507': ('ENTERPRISE-CORP, FR', 8192, 2**64, ['100.67.0.0/24'], [], 0.6),
    '64508': ('TELECOM-BACKBONE, CN', 4194304, 2**100, ['100.68.0.0/18', '100.68.64.0/18'], ['2001:db8:8000::/36'], 5.0),
    '64509': ('GAMING-HOSTING, UA', 16384, 2**72, ['100.69.0.0/23'], ['2001:db8:900::/48'], 7.0),
    '64510': ('CDN-EDGE, US', 524288, 2**92, ['100.70.0.0/21'], ['2001:db8:a00::/44'], 0.8),
    '64511': ('BROADBAND-ISP-D, VN', 1048576, 2**96, ['100.71.0.0/20'], ['2001:db8:b00::/40'], 3.5),
}


def random_ips(prefix: str, n: int):
    net = ip_network(prefix)
    size = min(net.num_addresses, 2**32)
    return {str(net[random.randrange(1, size - 1)]) for _ in range(n)}


def clear(storage: Redis, ranking: Redis, cache: Redis):
    for r in (storage, ranking):
        keys = r.smembers(DEMO_TAG)
        if keys:
            r.delete(*keys)
        r.delete(DEMO_TAG)
    for asn in ASNS:
        storage.delete(f'{asn}|descriptions')
    cache.flushdb()
    print('Demo data removed.')


def seed(storage: Redis, ranking: Redis, cache: Redis):
    configs = load_all_modules_configs()
    sources = sorted(configs)
    today = date.today()
    s_keys, r_keys = set(), set()

    for asn, (desc, *_rest) in ASNS.items():
        storage.hset(f'{asn}|descriptions', mapping={
            (today - timedelta(days=900)).isoformat() + 'T00:00:00': desc.replace(',', ' (old name),'),
            (today - timedelta(days=200)).isoformat() + 'T00:00:00': desc,
        })

    for i in range(DAYS):
        day = (today - timedelta(days=i)).isoformat()
        # A few lists have no data some days, like in real life.
        day_sources = [s for s in sources if random.random() > 0.25]
        storage.sadd(f'{day}|sources', *day_sources)
        s_keys.add(f'{day}|sources')
        wave = 1 + 0.6 * random.random() + (0.8 if i % 9 == 0 else 0)  # occasional peaks
        for source in day_sources:
            impact = configs[source]['impact']
            for asn, (desc, v4count, v6count, p4, p6, badness) in ASNS.items():
                if random.random() > 0.55:
                    continue
                rank = {'v4': 0.0, 'v6': 0.0}
                for prefix in p4 + p6:
                    net = ip_network(prefix)
                    n = max(1, int(random.expovariate(1 / (badness * wave))))
                    if net.version == 6 and random.random() > 0.3:
                        continue
                    ips = random_ips(prefix, n)
                    k = f'{day}|{source}|{asn}|{prefix}'
                    storage.sadd(k, *[f'{ip}|{day}T{random.randint(0, 23):02d}:00:00' for ip in ips])
                    s_keys.add(k)
                    v = f'v{net.version}'
                    prefix_rank = len(ips) / net.num_addresses
                    ranking.zadd(f'{day}|{source}|{asn}|{v}|prefixes', {prefix: prefix_rank})
                    ranking.zincrby(f'{day}|{asn}|{v}', prefix_rank * impact, prefix)
                    r_keys.update([f'{day}|{source}|{asn}|{v}|prefixes', f'{day}|{asn}|{v}'])
                    rank[v] += len(ips) * impact
                for v, count in (('v4', v4count), ('v6', v6count)):
                    if rank[v] and count:
                        value = rank[v] / count
                        ranking.set(f'{day}|{source}|{asn}|{v}', value)
                        ranking.zincrby(f'{day}|asns|{v}', value, asn)
                        ranking.zadd(f'{day}|{source}|asns|{v}', {asn: value})
                        r_keys.update([f'{day}|{source}|{asn}|{v}', f'{day}|asns|{v}', f'{day}|{source}|asns|{v}'])
                storage.sadd(f'{day}|{source}', asn)
                s_keys.add(f'{day}|{source}')
    storage.sadd(DEMO_TAG, *s_keys)
    ranking.sadd(DEMO_TAG, *r_keys)
    cache.flushdb()
    print(f'Demo data written: {DAYS} days, {len(ASNS)} ASNs, {len(sources)} sources.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--clear', action='store_true', help='Remove the demo data.')
    args = parser.parse_args()
    storage = Redis(get_config('generic', 'storage_db_hostname'), get_config('generic', 'storage_db_port'), decode_responses=True)
    ranking = Redis(get_config('generic', 'ranking_db_hostname'), get_config('generic', 'ranking_db_port'), decode_responses=True)
    cache = Redis(unix_socket_path=get_socket_path('cache'), db=1)
    if args.clear:
        clear(storage, ranking, cache)
    else:
        seed(storage, ranking, cache)
