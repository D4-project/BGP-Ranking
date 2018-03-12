#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from redis import Redis

from .libs.StatsRipe import StatsRIPE


class RoutingInformationServiceFetcher():

    def __init__(self, loglevel: int=logging.DEBUG):
        self.__init_logger(loglevel)
        self.ris_cache = Redis(host='localhost', port=6381, db=0)
        self.logger.debug('Starting RIS fetcher')
        self.ripe = StatsRIPE()

    def __init_logger(self, loglevel):
        self.logger = logging.getLogger('{}'.format(self.__class__.__name__))
        self.logger.setLevel(loglevel)

    async def fetch(self):
        while True:
            ip = self.ris_cache.spop('for_ris_lookup')
            if not ip:
                break
            ip = ip.decode()
            network_info = await self.ripe.network_info(ip)
            prefix = network_info['data']['prefix']
            asns = network_info['data']['asns']
            if not asns or not prefix:
                self.logger.warning('The IP {} does not seem to be announced'.format(ip))
                continue
            prefix_overview = await self.ripe.prefix_overview(prefix)
            description = prefix_overview['data']['block']['desc']
            if not description:
                description = prefix_overview['data']['block']['name']
            for asn in asns:
                self.ris_cache.hmset(ip, {'asn': asn, 'prefix': prefix,
                                          'description': description})
