#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

from bgpranking.abstractmanager import AbstractManager
from bgpranking.sanitizer import Sanitizer

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.WARNING, datefmt='%I:%M:%S')


class SanitizerManager(AbstractManager):

    def __init__(self, loglevel: int=logging.WARNING):
        super().__init__(loglevel)
        self.sanitizer = Sanitizer(loglevel)

    def _to_run_forever(self):
        self.sanitizer.sanitize()


if __name__ == '__main__':
    sanitizer = SanitizerManager()
    sanitizer.run(sleep_in_sec=120)
