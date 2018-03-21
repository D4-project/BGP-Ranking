#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import asyncio
from listimport.sanitizer import Sanitizer

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.WARNING, datefmt='%I:%M:%S')


class SanitizerManager():

    def __init__(self, loglevel: int=logging.WARNING):
        self.loglevel = loglevel
        self.sanitizer = Sanitizer(loglevel)

    async def run_sanitizer(self):
        await asyncio.gather(self.sanitizer.sanitize())


if __name__ == '__main__':
    modules_manager = SanitizerManager()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(modules_manager.run_sanitizer())
