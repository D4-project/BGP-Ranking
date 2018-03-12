#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import asyncio
from pathlib import Path
from listimport.parser import RawFilesParser

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')


class IntakeManager():

    def __init__(self, config_dir: Path=Path('listimport', 'modules_config'),
                 storage_directory: Path=Path('rawdata'),
                 loglevel: int=logging.DEBUG):
        self.config_dir = config_dir
        self.storage_directory = storage_directory
        self.loglevel = loglevel
        self.modules_paths = [modulepath for modulepath in self.config_dir.glob('*.json')]
        self.modules = [RawFilesParser(path, self.storage_directory, self.loglevel)
                        for path in self.modules_paths]

    async def run_intake(self):
        await asyncio.gather(
            *[module.parse_raw_files() for module in self.modules]
        )


if __name__ == '__main__':
    modules_manager = IntakeManager()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(modules_manager.run_intake())
