#!/usr/bin/env python
# -*- coding: utf-8 -*-

from dateutil import parser
from datetime import date
from pathlib import Path
from dateutil.relativedelta import relativedelta
from collections import defaultdict
import zipfile
import logging
import json

from .libs.helpers import safe_create_dir, set_running, unset_running


class DeepArchive():

    def __init__(self, config_file: Path, storage_directory: Path,
                 loglevel: int=logging.DEBUG):
        '''Archive everyfile older than 2 month.'''
        with open(config_file, 'r') as f:
            module_parameters = json.load(f)
        self.vendor = module_parameters['vendor']
        self.listname = module_parameters['name']
        self.directory = storage_directory / self.vendor / self.listname / 'archive'
        safe_create_dir(self.directory)
        self.deep_archive = self.directory / 'deep'
        safe_create_dir(self.deep_archive)
        self.__init_logger(loglevel)

    def __init_logger(self, loglevel):
        self.logger = logging.getLogger(f'{self.__class__.__name__}-{self.vendor}-{self.listname}')
        self.logger.setLevel(loglevel)

    def archive(self):
        set_running(self.__class__.__name__)

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
        unset_running(self.__class__.__name__)
