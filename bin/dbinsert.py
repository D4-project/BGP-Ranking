#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from bgpranking.abstractmanager import AbstractManager
from bgpranking.dbinsert import DatabaseInsert

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')


class DBInsertManager(AbstractManager):

    def __init__(self, loglevel: int=logging.INFO):
        super().__init__(loglevel)
        self.dbinsert = DatabaseInsert(loglevel)

    def _to_run_forever(self):
        self.dbinsert.insert()


if __name__ == '__main__':
    dbinsert = DBInsertManager()
    dbinsert.run(sleep_in_sec=120)
