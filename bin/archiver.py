#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import logging
import zipfile

from collections import defaultdict
from datetime import date
from logging import Logger
from pathlib import Path

from dateutil import parser
from dateutil.relativedelta import relativedelta

from bgpranking.default import safe_create_dir, AbstractManager
from bgpranking.helpers import get_modules, get_data_dir


logger = logging.getLogger('Archiver')
logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')


class DeepArchive():

    def __init__(self, config_file: Path, logger: Logger):
        '''Archive everyfile older than 2 month.'''
        with config_file.open() as f:
            module_parameters = json.load(f)
        self.logger = logger
        self.vendor = module_parameters['vendor']
        self.listname = module_parameters['name']
        self.directory = get_data_dir() / self.vendor / self.listname / 'archive'
        safe_create_dir(self.directory)
        self.deep_archive = self.directory / 'deep'
        safe_create_dir(self.deep_archive)

    def archive(self):
        to_archive = defaultdict(list)
        today = date.today()
        last_day_to_keep = date(today.year, today.month, 1) - relativedelta(months=2)
        for p in self.directory.iterdir():
            if not p.is_file():
                continue
            filedate = parser.parse(p.name.split('.')[0]).date()
            if filedate >= last_day_to_keep:
                continue
            to_archive['{}.zip'.format(filedate.strftime('%Y%m'))].append(p)
        if to_archive:
            self.logger.info('Found old files. Archiving: {}'.format(', '.join(to_archive.keys())))
        else:
            self.logger.debug('No old files.')
        for archivename, path_list in to_archive.items():
            with zipfile.ZipFile(self.deep_archive / archivename, 'x', zipfile.ZIP_DEFLATED) as z:
                for f in path_list:
                    z.write(f, f.name)
            # Delete all the files if the archiving worked out properly
            [f.unlink() for f in path_list]


class ModulesArchiver(AbstractManager):

    def __init__(self, loglevel: int=logging.INFO):
        super().__init__(loglevel)
        self.script_name = 'archiver'
        self.modules = [DeepArchive(path, self.logger) for path in get_modules()]

    def _to_run_forever(self):
        [module.archive() for module in self.modules]


def main():
    archiver = ModulesArchiver()
    archiver.run(sleep_in_sec=360000)


if __name__ == '__main__':
    main()
