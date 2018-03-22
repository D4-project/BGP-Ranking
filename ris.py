#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from listimport.risfetcher import RISPrefixLookup

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')


class RISManager():

    def __init__(self, loglevel: int=logging.DEBUG):
        self.ris_fetcher = RISPrefixLookup(loglevel=loglevel)

    def run_fetcher(self):
        self.ris_fetcher.run()


if __name__ == '__main__':
    modules_manager = RISManager()
    modules_manager.run_fetcher()
