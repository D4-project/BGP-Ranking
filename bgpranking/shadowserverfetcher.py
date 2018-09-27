#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import aiohttp
import logging
from bs4 import BeautifulSoup
from dateutil.parser import parse
from typing import Tuple
from datetime import datetime, date
from pathlib import Path
from .libs.helpers import safe_create_dir, set_running, unset_running
import json


class ShadowServerFetcher():

    def __init__(self, user, password, config_path_modules: Path, storage_directory: Path,
                 loglevel: int=logging.DEBUG) -> None:
        self.__init_logger(loglevel)
        self.storage_directory = storage_directory
        self.config_path_modules = config_path_modules
        self.user = user
        self.password = password
        self.index_page = 'https://dl.shadowserver.org/reports/index.php'
        self.vendor = 'shadowserver'
        self.known_list_types = ('blacklist', 'botnet', 'cc', 'cisco', 'cwsandbox', 'drone',
                                 'microsoft', 'scan', 'sinkhole6', 'sinkhole')
        self.first_available_day = None
        self.last_available_day = None
        self.available_entries = {}

    def __init_logger(self, loglevel):
        self.logger = logging.getLogger(f'{self.__class__.__name__}')
        self.logger.setLevel(loglevel)

    async def __get_index(self):
        auth_details = {'user': self.user, 'password': self.password, 'login': 'Login'}
        async with aiohttp.ClientSession() as s:
            self.logger.debug('Fetching the index.')
            async with s.post(self.index_page, data=auth_details) as r:
                return await r.text()

    async def __build_daily_dict(self):
        html_index = await self.__get_index()
        soup = BeautifulSoup(html_index, 'html.parser')
        treeview = soup.find(id='treemenu1')
        for y in treeview.select('> li'):
            year = y.contents[0]
            for m in y.contents[1].select('> li'):
                month = m.contents[0]
                for d in m.contents[1].select('> li'):
                    day = d.contents[0]
                    date = parse(f'{year} {month} {day}').date()
                    self.available_entries[date.isoformat()] = []
                    for a in d.contents[1].find_all('a', href=True):
                        if not self.first_available_day:
                            self.first_available_day = date
                        self.last_available_day = date
                        self.available_entries[date.isoformat()].append((a['href'], a.string))
        self.logger.debug('Dictionary created.')

    def __normalize_day(self, day: Tuple[str, date, datetime]=None) -> str:
        if not day:
            if not self.last_available_day:
                raise Exception('Unable to figure out the last available day. You need to run build_daily_dict first')
            day = self.last_available_day
        else:
            if isinstance(day, str):
                day = parse(day).date()
            elif isinstance(day, datetime):
                day = day.date()
        return day.isoformat()

    def __split_name(self, name):
        type_content, country, list_type = name.split('-')
        if '_' in type_content:
            type_content, details_type = type_content.split('_', maxsplit=1)
            if '_' in details_type:
                details_type, sub = details_type.split('_', maxsplit=1)
                return list_type, country, (type_content, details_type, sub)
            return list_type, country, (type_content, details_type)
        return list_type, country, (type_content)

    def __check_config(self, filename: str) -> Path:
        self.logger.debug(f'Working on config for {filename}.')
        config = {'vendor': 'shadowserver', 'parser': '.parsers.shadowserver'}
        type_content, _, type_details = self.__split_name(filename)
        prefix = type_content.split('.')[0]
        config['name'] = '{}-{}'.format(prefix, '_'.join(type_details))

        main_type = type_details[0]
        if main_type not in self.known_list_types:
            self.logger.warning(f'Unknown type: {main_type}. Please update the config creator script.')
            return None

        if main_type == 'blacklist':
            config['impact'] = 5
        elif main_type == 'botnet':
            config['impact'] = 2
        elif main_type == 'cc':
            config['impact'] = 5
        elif main_type == 'cisco':
            config['impact'] = 3
        elif main_type == 'cwsandbox':
            config['impact'] = 5
        elif main_type == 'drone':
            config['impact'] = 2
        elif main_type == 'microsoft':
            config['impact'] = 3
        elif main_type == 'scan':
            config['impact'] = 1
        elif main_type == 'sinkhole6':
            config['impact'] = 2
        elif main_type == 'sinkhole':
            config['impact'] = 2
        if not (self.config_path_modules / f"{config['vendor']}_{config['name']}.json").exists():
            self.logger.debug(f'Creating config file for {filename}.')
            with open(self.config_path_modules / f"{config['vendor']}_{config['name']}.json", 'w') as f:
                json.dump(config, f, indent=2)
        else:
            with open(self.config_path_modules / f"{config['vendor']}_{config['name']}.json", 'r') as f:
                # Validate new config file with old
                config_current = json.load(f)
                if config_current != config:
                    self.logger.warning('The config file created by this script is different from the one on disk: \n{}\n{}'.format(json.dumps(config), json.dumps(config_current)))
        # Init list directory
        directory = self.storage_directory / config['vendor'] / config['name']
        safe_create_dir(directory)
        meta = directory / 'meta'
        safe_create_dir(meta)
        archive_dir = directory / 'archive'
        safe_create_dir(archive_dir)
        self.logger.debug(f'Done with config for {filename}.')
        return directory

    async def download_daily_entries(self, day: Tuple[str, date, datetime]=None):
        set_running(f'{self.__class__.__name__}')
        await self.__build_daily_dict()
        for url, filename in self.available_entries[self.__normalize_day(day)]:
            storage_dir = self.__check_config(filename)
            if not storage_dir:
                continue
            # Check if the file we're trying to download has already been downloaded. Skip if True.
            uuid = url.split('/')[-1]
            if (storage_dir / 'meta' / 'last_download').exists():
                with open(storage_dir / 'meta' / 'last_download') as f:
                    last_download_uuid = f.read()
                if last_download_uuid == uuid:
                    self.logger.debug(f'Already downloaded: {url}.')
                    continue
            async with aiohttp.ClientSession() as s:
                async with s.get(url) as r:
                    self.logger.info(f'Downloading {url}.')
                    content = await r.content.read()
                    with (storage_dir / '{}.txt'.format(datetime.now().isoformat())).open('wb') as f:
                        f.write(content)
                    with open(storage_dir / 'meta' / 'last_download', 'w') as f:
                        f.write(uuid)
        unset_running(f'{self.__class__.__name__}')
