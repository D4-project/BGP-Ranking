#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import asyncio
from pathlib import Path
import aiohttp

from bgpranking.abstractmanager import AbstractManager
from bgpranking.modulesfetcher import Fetcher
from bgpranking.libs.helpers import get_config_path, get_list_storage_path

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')


class ModulesManager(AbstractManager):

    def __init__(self, config_dir: Path=None, storage_directory: Path=None, loglevel: int=logging.DEBUG):
        super().__init__(loglevel)
        if not config_dir:
            config_dir = get_config_path()
        if not storage_directory:
            storage_directory = get_list_storage_path()
        modules_config = config_dir / 'modules'
        modules_paths = [modulepath for modulepath in modules_config.glob('*.json')]
        self.modules = [Fetcher(path, storage_directory, loglevel) for path in modules_paths]

    def _to_run_forever(self):
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(asyncio.gather(
                *[module.fetch_list() for module in self.modules if module.fetcher])
            )
        except aiohttp.client_exceptions.ClientConnectorError as e:
            self.logger.critical('Exception while fetching lists: {}'.format(e))
        finally:
            loop.close()


if __name__ == '__main__':
    modules_manager = ModulesManager()
    modules_manager.run(sleep_in_sec=3600)
