#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from abc import ABC


class RIPECaching(ABC):

    def __init__(self, sourceapp: str='bgpranking-ng', loglevel: int=logging.DEBUG):
        self.sourceapp = sourceapp
        self.hostname = 'stat.ripe.net'
        self.port = 43
        self.__init_logger(loglevel)

    def __init_logger(self, loglevel):
        self.logger = logging.getLogger('{}'.format(self.__class__.__name__))
        self.logger.setLevel(loglevel)
