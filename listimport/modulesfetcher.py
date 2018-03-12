#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
from dateutil import parser
from datetime import datetime, date
from hashlib import sha512  # Faster than sha256 on 64b machines.
from pathlib import Path
import logging
import asyncio
from pid import PidFile, PidFileError
import json

from .libs.helpers import safe_create_dir


class Fetcher():

    def __init__(self, config_file: Path, storage_directory: Path,
                 loglevel: int=logging.DEBUG):
        '''Load `config_file`, and store the fetched data into `storage_directory`
        Note: if the `config_file` does not provide a URL (the file is
              gathered by some oter mean), the fetcher is automatically stoped.'''
        with open(config_file, 'r') as f:
            module_parameters = json.load(f)
        self.vendor = module_parameters['vendor']
        self.listname = module_parameters['name']
        self.__init_logger(loglevel)
        self.fetcher = True
        if 'url' not in module_parameters:
            self.logger.info('No URL to fetch, breaking.')
            self.fetcher = False
            return
        self.url = module_parameters['url']
        self.logger.debug('Starting fetcher on {}'.format(self.url))
        self.directory = storage_directory / self.vendor / self.listname
        safe_create_dir(self.directory)
        self.meta = self.directory / 'meta'
        safe_create_dir(self.meta)
        self.archive_dir = self.directory / 'archive'
        safe_create_dir(self.archive_dir)
        self.first_fetch = True

    def __init_logger(self, loglevel):
        self.logger = logging.getLogger('{}-{}-{}'.format(self.__class__.__name__,
                                                          self.vendor, self.listname))
        self.logger.setLevel(loglevel)

    def __get_last_modified(self):
        r = requests.head(self.url)
        if 'Last-Modified' in r.headers:
            return parser.parse(r.headers['Last-Modified'])
        return None

    def __newer(self):
        '''Check if the file available for download is newed than the one
        already downloaded by checking the `Last-Modified` header.
        Note: return False if the file containing the last header content
            is not existing, or the header doesn't have this key.
        '''
        last_modified_path = self.meta / 'lastmodified'
        if not last_modified_path.exists():
            # The file doesn't exists
            if not self.first_fetch:
                # The URL has no Last-Modified header, we cannot use it.
                self.logger.debug('No Last-Modified header available')
                return True
            self.first_fetch = False
            last_modified = self.__get_last_modified()
            if last_modified:
                self.logger.debug('Last-Modified header available')
                with last_modified_path.open('w') as f:
                    f.write(last_modified.isoformat())
            else:
                self.logger.debug('No Last-Modified header available')
            return True
        with last_modified_path.open() as f:
            last_modified_file = parser.parse(f.read())
        last_modified = self.__get_last_modified()
        if not last_modified:
            # No more Last-Modified header Oo
            self.logger.warning('{}: Last-Modified header was present, isn\'t anymore!'.format(self.listname))
            last_modified_path.unlink()
            return True
        if last_modified > last_modified_file:
            self.logger.info('Got a new file.')
            with last_modified_path.open('w') as f:
                f.write(last_modified.isoformat())
            return True
        return False

    def __same_as_last(self, downloaded):
        '''Figure out the last downloaded file, check if it is the same as the
        newly downloaded one. Returns true if both files have been downloaded the
        same day.
        Note: we check the new and the archive directory because we may have backlog
            and the newest file is always the first one we process
        '''
        to_check = []
        to_check_new = sorted([f for f in self.directory.iterdir() if f.is_file()])
        if to_check_new:
            # we have files waiting to be processed
            self.logger.debug('{} file(s) are waiting to be processed'.format(len(to_check_new)))
            to_check.append(to_check_new[-1])
        to_check_archive = sorted([f for f in self.archive_dir.iterdir() if f.is_file()])
        if to_check_archive:
            # we have files already processed, in the archive
            self.logger.debug('{} file(s) have been processed'.format(len(to_check_archive)))
            to_check.append(to_check_archive[-1])
        if not to_check:
            self.logger.debug('New list, no hisorical files')
            # nothing has been downloaded ever, moving on
            return False
        for last_file in to_check:
            with last_file.open('rb') as f:
                last_hash = sha512(f.read())
            dl_hash = sha512(downloaded)
            if (dl_hash.digest() == last_hash.digest() and
                    parser.parse(last_file.name.split('.')[0]).date() == date.today()):
                self.logger.debug('Same file already downloaded today.')
                return True
        return False

    @asyncio.coroutine
    async def fetch_list(self):
        '''Fetch & store the list'''
        if not self.fetcher:
            return
        try:
            with PidFile('{}.pid'.format(self.listname), piddir=self.meta):
                if not self.__newer():
                    return
                r = requests.get(self.url)
                if self.__same_as_last(r.content):
                    return
                self.logger.info('Got a new file \o/')
                with (self.directory / '{}.txt'.format(datetime.now().isoformat())).open('wb') as f:
                    f.write(r.content)
        except PidFileError:
            self.logger.info('Fetcher already running')
