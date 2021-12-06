#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import asyncio
import logging

from datetime import datetime, date
from hashlib import sha512  # Faster than sha256 on 64b machines.
from logging import Logger
from pathlib import Path

import aiohttp
from dateutil import parser
from pid import PidFile, PidFileError  # type: ignore

from bgpranking.default import AbstractManager, safe_create_dir
from bgpranking.helpers import get_modules, get_data_dir, get_modules_dir


logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')


class Fetcher():

    def __init__(self, config_file: Path, logger: Logger):
        '''Load `config_file`, and store the fetched data into `storage_directory`
        Note: if the `config_file` does not provide a URL (the file is
              gathered by some oter mean), the fetcher is automatically stoped.'''
        with open(config_file, 'r') as f:
            module_parameters = json.load(f)
        self.vendor = module_parameters['vendor']
        self.listname = module_parameters['name']
        self.logger = logger
        self.fetcher = True
        if 'url' not in module_parameters:
            self.logger.info(f'{self.vendor}-{self.listname}: No URL to fetch, breaking.')
            self.fetcher = False
            return
        self.url = module_parameters['url']
        self.logger.debug(f'{self.vendor}-{self.listname}: Starting fetcher on {self.url}')
        self.directory = get_data_dir() / self.vendor / self.listname
        safe_create_dir(self.directory)
        self.meta = self.directory / 'meta'
        safe_create_dir(self.meta)
        self.archive_dir = self.directory / 'archive'
        safe_create_dir(self.archive_dir)
        self.first_fetch = True

    async def __get_last_modified(self):
        async with aiohttp.ClientSession() as session:
            async with session.head(self.url) as r:
                headers = r.headers
                if 'Last-Modified' in headers:
                    return parser.parse(headers['Last-Modified'])
                return None

    async def __newer(self):
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
                self.logger.debug(f'{self.vendor}-{self.listname}: No Last-Modified header available')
                return True
            self.first_fetch = False
            last_modified = await self.__get_last_modified()
            if last_modified:
                self.logger.debug(f'{self.vendor}-{self.listname}: Last-Modified header available')
                with last_modified_path.open('w') as f:
                    f.write(last_modified.isoformat())
            else:
                self.logger.debug(f'{self.vendor}-{self.listname}: No Last-Modified header available')
            return True
        with last_modified_path.open() as f:
            file_content = f.read()
            last_modified_file = parser.parse(file_content)
        last_modified = await self.__get_last_modified()
        if not last_modified:
            # No more Last-Modified header Oo
            self.logger.warning(f'{self.vendor}-{self.listname}: Last-Modified header was present, isn\'t anymore!')
            last_modified_path.unlink()
            return True
        if last_modified > last_modified_file:
            self.logger.info(f'{self.vendor}-{self.listname}: Got a new file.')
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
            self.logger.debug(f'{self.vendor}-{self.listname}: {len(to_check_new)} file(s) are waiting to be processed')
            to_check.append(to_check_new[-1])
        to_check_archive = sorted([f for f in self.archive_dir.iterdir() if f.is_file()])
        if to_check_archive:
            # we have files already processed, in the archive
            self.logger.debug(f'{self.vendor}-{self.listname}: {len(to_check_archive)} file(s) have been processed')
            to_check.append(to_check_archive[-1])
        if not to_check:
            self.logger.debug(f'{self.vendor}-{self.listname}: New list, no hisorical files')
            # nothing has been downloaded ever, moving on
            return False
        dl_hash = sha512(downloaded)
        for last_file in to_check:
            with last_file.open('rb') as f:
                last_hash = sha512(f.read())
            if (dl_hash.digest() == last_hash.digest()
                    and parser.parse(last_file.name.split('.')[0]).date() == date.today()):
                self.logger.debug(f'{self.vendor}-{self.listname}: Same file already downloaded today.')
                return True
        return False

    async def fetch_list(self):
        '''Fetch & store the list'''
        if not self.fetcher:
            return
        try:
            with PidFile(f'{self.listname}.pid', piddir=self.meta):
                if not await self.__newer():
                    return
                async with aiohttp.ClientSession() as session:
                    async with session.get(self.url) as r:
                        content = await r.content.read()
                        if self.__same_as_last(content):
                            return
                        self.logger.info(f'{self.vendor}-{self.listname}: Got a new file!')
                        with (self.directory / '{}.txt'.format(datetime.now().isoformat())).open('wb') as f:
                            f.write(content)
        except PidFileError:
            self.logger.info(f'{self.vendor}-{self.listname}: Fetcher already running')


class ModulesManager(AbstractManager):

    def __init__(self, loglevel: int=logging.DEBUG):
        super().__init__(loglevel)
        self.script_name = 'modules_manager'
        self.modules_paths = get_modules()
        self.modules = [Fetcher(path, self.logger) for path in self.modules_paths]

    async def _to_run_forever_async(self):
        # Check if there are new config files
        new_modules_paths = [modulepath for modulepath in get_modules_dir().glob('*.json') if modulepath not in self.modules_paths]
        self.modules += [Fetcher(path, self.logger) for path in new_modules_paths]
        self.modules_paths += new_modules_paths

        if self.modules:
            for module in self.modules:
                if module.fetcher:
                    await module.fetch_list()
        else:
            self.logger.info('No config files were found so there are no fetchers running yet. Will try again later.')


def main():
    m = ModulesManager()
    asyncio.run(m.run_async(sleep_in_sec=3600))


if __name__ == '__main__':
    main()
