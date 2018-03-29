#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from bgpranking.dbinsert import DatabaseInsert
from bgpranking.libs.helpers import long_sleep, shutdown_requested

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')


class DBInsertManager():

    def __init__(self, loglevel: int=logging.DEBUG):
        self.loglevel = loglevel
        self.dbinsert = DatabaseInsert(loglevel)

    def run_insert(self):
        self.dbinsert.insert()


if __name__ == '__main__':
    modules_manager = DBInsertManager()
    while True:
        if shutdown_requested():
            break
        modules_manager.run_insert()
        if not long_sleep(120):
            break
