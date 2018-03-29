#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from pathlib import Path
from bgpranking.parser import RawFilesParser
from bgpranking.libs.helpers import get_config_path, get_list_storage_path
from bgpranking.libs.helpers import long_sleep, shutdown_requested

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')


class ParserManager():

    def __init__(self, config_dir: Path=None, storage_directory: Path=None, loglevel: int=logging.DEBUG):
        if not config_dir:
            config_dir = get_config_path()
        if not storage_directory:
            storage_directory = get_list_storage_path()
        modules_config = config_dir / 'modules'
        modules_paths = [modulepath for modulepath in modules_config.glob('*.json')]
        self.modules = [RawFilesParser(path, storage_directory, loglevel) for path in modules_paths]

    def run_intake(self):
        [module.parse_raw_files() for module in self.modules]


if __name__ == '__main__':
    parser_manager = ParserManager()
    while True:
        if shutdown_requested():
            break
        parser_manager.run_intake()
        if not long_sleep(120):
            break
