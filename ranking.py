#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from listimport.initranking import PrefixDatabase


logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')


class RankingManager():

    def __init__(self, loglevel: int=logging.DEBUG):
        self.prefix_db = PrefixDatabase(loglevel=loglevel)

    def load_prefixes(self):
        self.prefix_db.load_prefixes()


if __name__ == '__main__':
    rm = RankingManager()
    rm.load_prefixes()
