#!/usr/bin/env python
# -*- coding: utf-8 -*-

from abc import ABC, abstractmethod
import logging

from .libs.helpers import long_sleep, shutdown_requested


class AbstractManager(ABC):

    def __init__(self, loglevel: int=logging.DEBUG):
        self.logger = logging.getLogger('{}'.format(self.__class__.__name__))
        self.logger.setLevel(loglevel)
        self.logger.info('Initializing {}'.format(self.__class__.__name__))

    @abstractmethod
    def _to_run_forever(self):
        pass

    def run(self, sleep_in_sec: int):
        self.logger.info('Launching {}'.format(self.__class__.__name__))
        while True:
            if shutdown_requested():
                break
            try:
                self._to_run_forever()
            except Exception:
                self.logger.exception('Something went terribly wrong in {}.'.format(self.__class__.__name__))
            if not long_sleep(sleep_in_sec):
                break
        self.logger.info('Shutting down {}'.format(self.__class__.__name__))
