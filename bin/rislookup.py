#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from bgpranking.risfetcher import RISPrefixLookup
from bgpranking.libs.helpers import long_sleep, shutdown_requested

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')


class RISLookupManager():

    def __init__(self, loglevel: int=logging.INFO):
        self.ris_fetcher = RISPrefixLookup(loglevel=loglevel)

    def run_fetcher(self):
        self.ris_fetcher.run()


if __name__ == '__main__':
    modules_manager = RISLookupManager()
    while True:
        if shutdown_requested():
            break
        modules_manager.run_fetcher()
        if not long_sleep(120):
            break
