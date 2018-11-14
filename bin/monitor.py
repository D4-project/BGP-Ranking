#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from bgpranking.monitor import Monitor
import logging

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')


class MonitorManager():

    def __init__(self, loglevel: int=logging.INFO):
        self.monitor = Monitor()

    def get_values(self):
        return self.monitor.get_values()


if __name__ == '__main__':
    m = MonitorManager()
    print(m.get_values())
