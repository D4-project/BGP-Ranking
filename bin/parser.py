#!/usr/bin/env python3
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
            self.storage_directory = get_homedir() / 'rawdata'
        self.modules_config = config_dir / 'modules'
        self.modules_paths = [modulepath for modulepath in self.modules_config.glob('*.json')]
        self.modules = [RawFilesParser(path, self.storage_directory, loglevel) for path in self.modules_paths]

    def _to_run_forever(self):
        # Check if there are new config files
        new_modules_paths = [modulepath for modulepath in self.modules_config.glob('*.json') if modulepath not in self.modules_paths]
        self.modules += [RawFilesParser(path, self.storage_directory, self.loglevel) for path in new_modules_paths]
        self.modules_paths += new_modules_paths

        if self.modules:
            [module.parse_raw_files() for module in self.modules]
        else:
            self.logger.warning('No config files were found so there are no parsers running yet. Will try again later.')


if __name__ == '__main__':
    parser_manager = ParserManager()
    parser_manager.run(sleep_in_sec=120)
