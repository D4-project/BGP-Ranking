#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import asyncio
from listimport.initranking import ASNLookup


logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')


class RankingManager():

    def __init__(self, loglevel: int=logging.DEBUG):
        self.asn_fetcher = ASNLookup(loglevel=loglevel)

    async def run_fetcher(self):
        # self.asn_fetcher.get_all_asns()
        await asyncio.gather(
            self.asn_fetcher.get_originating_prefixes(),
            self.asn_fetcher.get_originating_prefixes(),
            self.asn_fetcher.get_originating_prefixes()
        )


if __name__ == '__main__':
    modules_manager = RankingManager()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(modules_manager.run_fetcher())
