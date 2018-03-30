#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging

from bgpranking.abstractmanager import AbstractManager
from bgpranking.risfetcher import RISPrefixLookup

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')


class RISLookupManager(AbstractManager):

    def __init__(self, loglevel: int=logging.INFO):
        super().__init__(loglevel)
        self.ris_fetcher = RISPrefixLookup(loglevel=loglevel)

    def _to_run_forever(self):
        self.ris_fetcher.run()


if __name__ == '__main__':
    rislookup = RISLookupManager()
    rislookup.run(120)
