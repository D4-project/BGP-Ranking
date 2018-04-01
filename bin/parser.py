#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from pathlib import Path

from bgpranking.abstractmanager import AbstractManager
from bgpranking.parser import RawFilesParser
from bgpranking.libs.helpers import get_config_path, get_homedir

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')


class ParserManager(AbstractManager):

    def __init__(self, config_dir: Path=None, storage_directory: Path=None, loglevel: int=logging.DEBUG):
        super().__init__(loglevel)
        if not config_dir:
            config_dir = get_config_path()
        if not storage_directory:
            storage_directory = get_homedir() / 'rawdata'
        modules_config = config_dir / 'modules'
        modules_paths = [modulepath for modulepath in modules_config.glob('*.json')]
        self.modules = [RawFilesParser(path, storage_directory, loglevel) for path in modules_paths]

    def _to_run_forever(self):
        [module.parse_raw_files() for module in self.modules]


if __name__ == '__main__':
    parser_manager = ParserManager()
    parser_manager.run(sleep_in_sec=120)
