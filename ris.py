#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import asyncio
from listimport.risfetcher import RoutingInformationServiceFetcher

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')


class RISManager():

    def __init__(self, loglevel: int=logging.DEBUG):
        self.ris_fetcher = RoutingInformationServiceFetcher(loglevel)

    async def run_fetcher(self):
        await asyncio.gather(self.ris_fetcher.fetch())


if __name__ == '__main__':
    modules_manager = RISManager()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(modules_manager.run_fetcher())
