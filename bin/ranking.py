#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

from datetime import datetime, date, timedelta
from ipaddress import ip_network
from typing import Dict, Any

from redis import Redis
import requests

from bgpranking.default import AbstractManager, get_config
from bgpranking.helpers import get_ipasn, sanity_check_ipasn, load_all_modules_configs

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')


class Ranking(AbstractManager):

    def __init__(self, loglevel: int=logging.INFO):
        super().__init__(loglevel)
        self.script_name = 'ranking'
        self.storage = Redis(get_config('generic', 'storage_db_hostname'), get_config('generic', 'storage_db_port'), decode_responses=True)
        self.ranking = Redis(get_config('generic', 'ranking_db_hostname'), get_config('generic', 'ranking_db_port'), decode_responses=True)
        self.ipasn = get_ipasn()

    def rank_a_day(self, day: str):
        asns_aggregation_key_v4 = f'{day}|asns|v4'
        asns_aggregation_key_v6 = f'{day}|asns|v6'
        to_delete = set([asns_aggregation_key_v4, asns_aggregation_key_v6])
        r_pipeline = self.ranking.pipeline()
        cached_meta: Dict[str, Dict[str, Any]] = {}
        config_files = load_all_modules_configs()
        for source in self.storage.smembers(f'{day}|sources'):
            self.logger.info(f'{day} - Ranking source: {source}')
            source_aggregation_key_v4 = f'{day}|{source}|asns|v4'
            source_aggregation_key_v6 = f'{day}|{source}|asns|v6'
            to_delete.update([source_aggregation_key_v4, source_aggregation_key_v6])
            for asn in self.storage.smembers(f'{day}|{source}'):
                prefixes_aggregation_key_v4 = f'{day}|{asn}|v4'
                prefixes_aggregation_key_v6 = f'{day}|{asn}|v6'
                to_delete.update([prefixes_aggregation_key_v4, prefixes_aggregation_key_v6])
                if asn == '0':
                    # Default ASN when no matches. Probably spoofed.
                    continue
                self.logger.debug(f'{day} - Ranking source: {source} / ASN: {asn}')
                asn_rank_v4 = 0.0
                asn_rank_v6 = 0.0
                for prefix in self.storage.smembers(f'{day}|{source}|{asn}'):
                    if prefix == 'None':
                        # This should not happen and requires a DB cleanup.
                        self.logger.critical(f'Fucked up prefix in "{day}|{source}|{asn}"')
                        continue
                    ips = set([ip_ts.split('|')[0]
                               for ip_ts in self.storage.smembers(f'{day}|{source}|{asn}|{prefix}')])
                    py_prefix = ip_network(prefix)
                    prefix_rank = float(len(ips)) / py_prefix.num_addresses
                    r_pipeline.zadd(f'{day}|{source}|{asn}|v{py_prefix.version}|prefixes', {prefix: prefix_rank})
                    if py_prefix.version == 4:
                        asn_rank_v4 += len(ips) * config_files[source]['impact']
                        r_pipeline.zincrby(prefixes_aggregation_key_v4, prefix_rank * config_files[source]['impact'], prefix)
                    else:
                        asn_rank_v6 += len(ips) * config_files[source]['impact']
                        r_pipeline.zincrby(prefixes_aggregation_key_v6, prefix_rank * config_files[source]['impact'], prefix)
                if asn in cached_meta:
                    v4info = cached_meta[asn]['v4']
                    v6info = cached_meta[asn]['v6']
                else:
                    retry = 3
                    while retry:
                        try:
                            v4info = self.ipasn.asn_meta(asn=asn, source='caida', address_family='v4', date=day)
                            v6info = self.ipasn.asn_meta(asn=asn, source='caida', address_family='v6', date=day)
                            break
                        except requests.exceptions.ConnectionError:
                            # Sometimes, ipasnhistory is unreachable try again a few times
                            retry -= 1
                    else:
                        # if it keeps failing, the ASN will be ranked on next run.
                        continue

                    cached_meta[asn] = {'v4': v4info, 'v6': v6info}
                ipasnhistory_date_v4 = list(v4info['response'].keys())[0]
                v4count = v4info['response'][ipasnhistory_date_v4][asn]['ipcount']
                ipasnhistory_date_v6 = list(v6info['response'].keys())[0]
                v6count = v6info['response'][ipasnhistory_date_v6][asn]['ipcount']
                if v4count:
                    asn_rank_v4 /= float(v4count)
                    if asn_rank_v4:
                        r_pipeline.set(f'{day}|{source}|{asn}|v4', asn_rank_v4)
                        r_pipeline.zincrby(asns_aggregation_key_v4, asn_rank_v4, asn)
                        r_pipeline.zadd(source_aggregation_key_v4, {asn: asn_rank_v4})
                if v6count:
                    asn_rank_v6 /= float(v6count)
                    if asn_rank_v6:
                        r_pipeline.set(f'{day}|{source}|{asn}|v6', asn_rank_v6)
                        r_pipeline.zincrby(asns_aggregation_key_v6, asn_rank_v6, asn)
                        r_pipeline.zadd(source_aggregation_key_v6, {asn: asn_rank_v6})
        self.ranking.delete(*to_delete)
        r_pipeline.execute()

    def compute(self):
        ready, message = sanity_check_ipasn(self.ipasn)
        if not ready:
            # Try again later.
            self.logger.warning(message)
            return
        self.logger.debug(message)

        self.logger.info('Start ranking')
        today = date.today()
        now = datetime.now()
        today12am = now.replace(hour=12, minute=0, second=0, microsecond=0)
        if now < today12am:
            # Compute yesterday and today's ranking (useful when we have lists generated only once a day)
            self.rank_a_day((today - timedelta(days=1)).isoformat())
        self.rank_a_day(today.isoformat())
        self.logger.info('Ranking done.')

    def _to_run_forever(self):
        self.compute()


def main():
    ranking = Ranking()
    ranking.run(sleep_in_sec=3600)


if __name__ == '__main__':
    main()
