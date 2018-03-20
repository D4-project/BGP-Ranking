#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import json
from redis import Redis

from .libs.StatsRipeText import RIPECaching
import asyncio


class RISPrefixLookup(RIPECaching):

    def __init__(self, sourceapp: str='bgpranking-ng', loglevel: int=logging.DEBUG):
        super().__init__(sourceapp, loglevel)
        self.logger.debug('Starting RIS Prefix fetcher')

    def cache_prefix(self, redis_cache, ip, network_info, prefix_overview):
        prefix = network_info['prefix']
        asns = network_info['asns']
        description = prefix_overview['block']['desc']
        if not description:
            description = prefix_overview['block']['name']
        p = redis_cache.pipeline()
        for asn in asns:
            p.hmset(ip, {'asn': asn, 'prefix': prefix, 'description': description})
            p.expire(ip, 43200)  # 12H
        p.execute()

    async def run(self):
        redis_cache = Redis(host='localhost', port=6381, db=0, decode_responses=True)
        reader, writer = await asyncio.open_connection(self.hostname, self.port)

        writer.write(b'-k\n')
        while True:
            ip = redis_cache.spop('for_ris_lookup')
            if not ip:  # TODO: add a check against something to stop the loop
                self.logger.debug('Nothing to lookup')
                await asyncio.sleep(10)
                continue
            if redis_cache.exists(ip):
                self.logger.debug('Already cached: {}'.format(ip))
                continue
            self.logger.debug('RIS lookup: {}'.format(ip))
            to_send = '-d network-info {} sourceapp={}\n'.format(ip, self.sourceapp)
            writer.write(to_send.encode())
            data = await reader.readuntil(b'\n}\n')
            network_info = json.loads(data)
            if not network_info.get('prefix'):
                self.logger.warning('The IP {} does not seem to be announced'.format(ip))
                continue
            self.logger.debug('Prefix lookup: {}'.format(ip))
            to_send = '-d prefix-overview {} sourceapp={}\n'.format(network_info['prefix'], self.sourceapp)
            writer.write(to_send.encode())
            data = await reader.readuntil(b'\n}\n')
            prefix_overview = json.loads(data)
            self.logger.debug('RIS cache prefix info: {}'.format(ip))
            self.cache_prefix(redis_cache, ip, network_info, prefix_overview)
        writer.write(b'-k\n')
        writer.close()
