#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import json
import asyncio
from pathlib import Path
import aiohttp

from bgpranking.abstractmanager import AbstractManager
from bgpranking.shadowserverfetcher import ShadowServerFetcher
from bgpranking.libs.helpers import get_config_path, get_homedir

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')


class ShadowServerManager(AbstractManager):

    def __init__(self, config_dir: Path=None, storage_directory: Path=None, loglevel: int=logging.INFO):
        super().__init__(loglevel)
        self.config = True
        if not config_dir:
            config_dir = get_config_path()
        if not (config_dir / 'shadowserver.json').exists():
            self.config = False
            self.logger.warning(f'No config file available, the shadow server module will not be launched.')
            return
        with open(config_dir / 'shadowserver.json') as f:
            ss_config = json.load(f)
        if not storage_directory:
            storage_directory = get_homedir() / 'rawdata'
        modules_config = config_dir / 'modules'
        self.fetcher = ShadowServerFetcher(ss_config['user'], ss_config['password'], modules_config, storage_directory, loglevel)

    def _to_run_forever(self):
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(self.fetcher.download_daily_entries())
        except aiohttp.client_exceptions.ClientConnectorError as e:
            self.logger.critical(f'Exception while fetching Shadow Server lists: {e}')


if __name__ == '__main__':
    modules_manager = ShadowServerManager()
    if modules_manager.config:
        modules_manager.run(sleep_in_sec=3600)
