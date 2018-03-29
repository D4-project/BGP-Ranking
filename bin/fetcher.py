#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import asyncio
from pathlib import Path
from bgpranking.libs.helpers import long_sleep, shutdown_requested
import aiohttp

from bgpranking.modulesfetcher import Fetcher
from bgpranking.libs.helpers import get_config_path, get_list_storage_path

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')

logger = logging.getLogger('Fetcher')


class ModulesManager():

    def __init__(self, config_dir: Path=None, storage_directory: Path=None, loglevel: int=logging.DEBUG):
        if not config_dir:
            config_dir = get_config_path()
        if not storage_directory:
            storage_directory = get_list_storage_path()
        modules_config = config_dir / 'modules'
        modules_paths = [modulepath for modulepath in modules_config.glob('*.json')]
        self.modules = [Fetcher(path, storage_directory, loglevel) for path in modules_paths]

    async def run_fetchers(self):
        await asyncio.gather(
            *[module.fetch_list() for module in self.modules if module.fetcher]
        )


if __name__ == '__main__':
    modules_manager = ModulesManager()
    loop = asyncio.get_event_loop()
    while True:
        if shutdown_requested():
            break
        try:
            loop.run_until_complete(modules_manager.run_fetchers())
        except aiohttp.client_exceptions.ClientConnectorError:
            logger.critical('Exception while fetching lists.')
            long_sleep(60)
            continue
        if not long_sleep(3600):
            break
