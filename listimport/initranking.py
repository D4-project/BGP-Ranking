#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import json
from redis import Redis
import asyncio

from telnetlib import Telnet

from .libs.StatsRipeText import RIPECaching
from ipaddress import ip_network


class ASNLookup(RIPECaching):

    def __init__(self, sourceapp: str='bgpranking-ng', loglevel: int=logging.DEBUG):
        super().__init__(sourceapp, loglevel)
        self.redis_cache = Redis(host='localhost', port=6382, db=0, decode_responses=True)
        self.logger.debug('Starting ASN lookup cache')

    def get_all_asns(self):
        with Telnet(self.hostname, self.port) as tn:
            tn.write(b'-k\n')
            to_send = '-d ris-asns list_asns=true asn_types=o sourceapp={}\n'.format(self.sourceapp)
            tn.write(to_send.encode())
            ris_asns = json.loads(tn.read_until(b'\n}\n'))
            all_asns = ris_asns['asns']['originating']
            if not all_asns:
                self.logger.warning('No ASNs in ris-asns, something went wrong.')
            else:
                self.redis_cache.sadd('asns', *all_asns)
                self.redis_cache.sadd('asns_to_lookup', *all_asns)
            tn.write(b'-k\n')

    def fix_ipv4_networks(self, networks):
        '''Because we can't have nice things.
        Some netorks come without the last(s) bytes (i.e. 170.254.25/24)'''
        to_return = []
        for net in networks:
            try:
                to_return.append(ip_network(net))
            except ValueError:
                ip, mask = net.split('/')
                iplist = ip.split('.')
                iplist = iplist + ['0'] * (4 - len(iplist))
                to_return.append(ip_network('{}/{}'.format('.'.join(iplist), mask)))
        return to_return

    async def get_originating_prefixes(self):
        reader, writer = await asyncio.open_connection(self.hostname, self.port)
        writer.write(b'-k\n')
        while True:
            asn = self.redis_cache.spop('asns_to_lookup')
            if not asn:
                break
            self.logger.debug('ASN lookup: {}'.format(asn))
            to_send = '-d ris-prefixes {} list_prefixes=true types=o af=v4,v6 noise=filter sourceapp={}\n'.format(asn, self.sourceapp)
            writer.write(to_send.encode())
            data = await reader.readuntil(b'\n}\n')
            ris_prefixes = json.loads(data)
            p = self.redis_cache.pipeline()
            if ris_prefixes['prefixes']['v4']['originating']:
                self.logger.debug('{} has ipv4'.format(asn))
                fixed_networks = self.fix_ipv4_networks(ris_prefixes['prefixes']['v4']['originating'])
                p.sadd('{}|v4'.format(asn), *[str(net) for net in fixed_networks])
                total_ipv4 = sum([net.num_addresses for net in fixed_networks])
                p.set('{}|v4|ipcount'.format(asn), total_ipv4)
            if ris_prefixes['prefixes']['v6']['originating']:
                self.logger.debug('{} has ipv6'.format(asn))
                p.sadd('{}|v6'.format(asn), *ris_prefixes['prefixes']['v6']['originating'])
                total_ipv6 = sum([ip_network(prefix).num_addresses for prefix in ris_prefixes['prefixes']['v6']['originating']])
                p.set('{}|v4|ipcount'.format(asn), total_ipv6)
            p.execute()
        writer.write(b'-k\n')
        writer.close()
