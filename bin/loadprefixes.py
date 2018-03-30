#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import requests

from bgpranking.abstractmanager import AbstractManager
from bgpranking.prefixdb import PrefixDatabase

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')


class PrefixDBManager(AbstractManager):

    def __init__(self, loglevel: int=logging.DEBUG):
        super().__init__(loglevel)
        self.prefix_db = PrefixDatabase(loglevel=loglevel)

    def _to_run_forever(self):
        try:
            if self.prefix_db.update_required():
                self.prefix_db.load_prefixes()
        except requests.exceptions.ConnectionError as e:
            self.logger.critical('Unable to download the prefix database: {}'.format(e))


if __name__ == '__main__':
    p = PrefixDBManager()
    p.run(sleep_in_sec=3600)
