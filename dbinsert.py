#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import asyncio
from listimport.dbinsert import DatabaseInsert

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')


class DBInsertManager():

    def __init__(self, loglevel: int=logging.DEBUG):
        self.loglevel = loglevel
        self.dbinsert = DatabaseInsert(loglevel)

    async def run_insert(self):
        await asyncio.gather(self.dbinsert.insert())


if __name__ == '__main__':
    modules_manager = DBInsertManager()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(modules_manager.run_insert())
