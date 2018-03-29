#!/usr/bin/env python
# -*- coding: utf-8 -*-

from bgpranking.archive import DeepArchive
import logging
from pathlib import Path
from bgpranking.libs.helpers import get_config_path, get_list_storage_path
from pid import PidFile, PidFileError


logger = logging.getLogger('Archiver')
logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')

# NOTE:
# * Supposed to run once every ~2 months


class ModulesArchiver():

    def __init__(self, config_dir: Path=None, storage_directory: Path=None, loglevel: int=logging.INFO):
        if not config_dir:
            config_dir = get_config_path()
        if not storage_directory:
            self.storage_directory = get_list_storage_path()
        modules_config = config_dir / 'modules'
        modules_paths = [modulepath for modulepath in modules_config.glob('*.json')]
        self.modules = [DeepArchive(path, self.storage_directory, loglevel) for path in modules_paths]

    def archive(self):
        [module.archive() for module in self.modules]


if __name__ == '__main__':
    archiver = ModulesArchiver()
    try:
        with PidFile(piddir=archiver.storage_directory):
            logger.info('Archiving...')
            archiver.archive()
        logger.info('... done.')
    except PidFileError:
        logger.warning('Archiver already running, skip.')
