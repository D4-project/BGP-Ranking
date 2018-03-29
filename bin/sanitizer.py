#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from bgpranking.sanitizer import Sanitizer
from bgpranking.libs.helpers import long_sleep, shutdown_requested

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.WARNING, datefmt='%I:%M:%S')


class SanitizerManager():

    def __init__(self, loglevel: int=logging.WARNING):
        self.loglevel = loglevel
        self.sanitizer = Sanitizer(loglevel)

    def run_sanitizer(self):
        self.sanitizer.sanitize()


if __name__ == '__main__':
    modules_manager = SanitizerManager()
    while True:
        if shutdown_requested():
            break
        modules_manager.run_sanitizer()
        if not long_sleep(120):
            break
