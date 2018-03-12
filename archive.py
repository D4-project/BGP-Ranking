#!/usr/bin/env python
# -*- coding: utf-8 -*-

from listimport.archive import DeepArchive
import logging
from pathlib import Path

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')


class ModulesArchiver():

    def __init__(self, config_dir: Path=Path('listimport', 'modules_config'),
                 storage_directory: Path=Path('rawdata'),
                 loglevel: int=logging.INFO):
        self.config_dir = config_dir
        self.storage_directory = storage_directory
        self.loglevel = loglevel
        self.modules_paths = [modulepath for modulepath in self.config_dir.glob('*.json')]
        self.modules = [DeepArchive(path, self.storage_directory, self.loglevel)
                        for path in self.modules_paths]

    def archive(self):
        [module.archive() for module in self.modules]


if __name__ == '__main__':
    archiver = ModulesArchiver()
    archiver.archive()
