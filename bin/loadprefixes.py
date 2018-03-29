#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from bgpranking.prefixdb import PrefixDatabase
from bgpranking.libs.helpers import long_sleep, shutdown_requested
import requests

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')

logger = logging.getLogger('PrefixDB Fetcher')


class PrefixDBManager():

    def __init__(self, loglevel: int=logging.DEBUG):
        self.prefix_db = PrefixDatabase(loglevel=loglevel)

    def load_prefixes(self):
        self.prefix_db.load_prefixes()

    def needs_update(self):
        return self.prefix_db.update_required()


if __name__ == '__main__':
    p = PrefixDBManager()
    while True:
        if shutdown_requested():
            break
        try:
            if p.needs_update():
                p.load_prefixes()
        except requests.exceptions.ConnectionError:
            logger.critical('Unable to download the prefix database.')
            long_sleep(60)
            continue
        if not long_sleep(3600):
            break
