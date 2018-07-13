#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from bgpranking.abstractmanager import AbstractManager
from bgpranking.ranking import Ranking
from pathlib import Path

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')


class RankingManager(AbstractManager):

    def __init__(self, config_dir: Path=None, loglevel: int=logging.INFO):
        super().__init__(loglevel)
        self.ranking = Ranking(config_dir, loglevel)

    def _to_run_forever(self):
        self.ranking.compute()


if __name__ == '__main__':
    dbinsert = RankingManager()
    dbinsert.run(sleep_in_sec=3600)
