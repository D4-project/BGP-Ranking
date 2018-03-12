#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import asyncio
from pathlib import Path

from listimport.modulesfetcher import Fetcher

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')


class ModulesManager():

    def __init__(self, config_dir: Path=Path('listimport', 'modules_config'),
                 storage_directory: Path=Path('rawdata'),
                 loglevel: int=logging.DEBUG):
        self.config_dir = config_dir
        print(config_dir)
        self.storage_directory = storage_directory
        self.loglevel = loglevel
        self.modules_paths = [modulepath for modulepath in self.config_dir.glob('*.json')]
        self.modules = [Fetcher(path, self.storage_directory, self.loglevel)
                        for path in self.modules_paths]

    async def run_fetchers(self):
        await asyncio.gather(
            *[module.fetch_list() for module in self.modules if module.fetcher]
        )


if __name__ == '__main__':
    modules_manager = ModulesManager()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(modules_manager.run_fetchers())
