#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import os
from dateutil import parser
from datetime import datetime, date
from hashlib import sha512  # Faster than sha256 on 64b machines.
from pathlib import Path
from dateutil.relativedelta import relativedelta
from collections import defaultdict
import zipfile
import logging
import asyncio
from pid import PidFile, PidFileError
import json
import re
from redis import Redis
from redis import StrictRedis
from uuid import uuid4
from io import BytesIO
import importlib

from typing import List
import types
import ipaddress


class BGPRankingException(Exception):
    pass


class FetcherException(BGPRankingException):
    pass


class ArchiveException(BGPRankingException):
    pass


class CreateDirectoryException(BGPRankingException):
    pass


"""
Directory structure:
storage_directory / vendor / listname -> files to import
storage_directory / vendor / listname / meta -> last modified & pid
storage_directory / vendor / listname / archive -> imported files <= 2 month old
storage_directory / vendor / listname / archive / deep -> imported files > 2 month old (zipped)
"""


def safe_create_dir(to_create: Path):
    if to_create.exists() and not to_create.is_dir():
        raise CreateDirectoryException('The path {} already exists and is not a directory'.format(to_create))
    os.makedirs(to_create, exist_ok=True)


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


# get announcer: https://stat.ripe.net/data/network-info/data.json?resource=149.13.33.14

class RawFilesParser():

    def __init__(self, config_file: Path, storage_directory: Path,
                 loglevel: int=logging.DEBUG):
        with open(config_file, 'r') as f:
            module_parameters = json.load(f)
        self.vendor = module_parameters['vendor']
        self.listname = module_parameters['name']
        if 'parser' in module_parameters:
            self.parse_raw_file = types.MethodType(importlib.import_module(module_parameters['parser']).parse_raw_file, self)
        self.source = '{}-{}'.format(self.vendor, self.listname)
        self.directory = storage_directory / self.vendor / self.listname
        safe_create_dir(self.directory)
        self.__init_logger(loglevel)
        self.redis_intake = Redis(host='localhost', port=6379, db=0)
        self.logger.debug('Starting intake on {}'.format(self.source))

    def __init_logger(self, loglevel):
        self.logger = logging.getLogger('{}-{}-{}'.format(self.__class__.__name__,
                                                          self.vendor, self.listname))
        self.logger.setLevel(loglevel)

    @property
    def files_to_parse(self) -> List[Path]:
        return sorted([f for f in self.directory.iterdir() if f.is_file()], reverse=True)

    def extract_ipv4(self, bytestream: bytes) -> List[bytes]:
        return re.findall(rb'[0-9]+(?:\.[0-9]+){3}', bytestream)

    def parse_raw_file(self, f: BytesIO):
        self.datetime = datetime.now()
        return self.extract_ipv4(f.getvalue())

    @asyncio.coroutine
    async def parse_raw_files(self):
        for filepath in self.files_to_parse:
            self.logger.debug('Parsing {}, {} to go.'.format(filepath, len(self.files_to_parse) - 1))
            with open(filepath, 'rb') as f:
                to_parse = BytesIO(f.read())
            p = self.redis_intake.pipeline()
            for ip in self.parse_raw_file(to_parse):
                uuid = uuid4()
                p.hmset(uuid, {'ip': ip, 'source': self.source,
                               'datetime': self.datetime.isoformat()})
                p.sadd('intake', uuid)
            p.execute()
            self._archive(filepath)

    def _archive(self, filepath: Path):
        '''After processing, move file to the archive directory'''
        filepath.rename(self.directory / 'archive' / filepath.name)


class Sanitizer():

    def __init__(self, loglevel: int=logging.DEBUG):
        self.__init_logger(loglevel)
        self.redis_intake = Redis(host='localhost', port=6379, db=0, decode_responses=True)
        self.redis_sanitized = Redis(host='localhost', port=6380, db=0, decode_responses=True)
        self.ris_cache = Redis(host='localhost', port=6381, db=0, decode_responses=True)
        self.logger.debug('Starting import')

    def __init_logger(self, loglevel):
        self.logger = logging.getLogger('{}'.format(self.__class__.__name__))
        self.logger.setLevel(loglevel)

    async def sanitize(self):
        while True:
            uuid = self.redis_intake.spop('intake')
            if not uuid:
                break
            data = self.redis_intake.hgetall(uuid)
            try:
                ip = ipaddress.ip_address(data['ip'])
            except ValueError:
                self.logger.info('Invalid IP address: {}'.format(data['ip']))
                continue
            if not ip.is_global:
                self.logger.info('The IP address {} is not global'.format(data['ip']))
                continue

            date = parser.parse(data['datetime']).date().isoformat()
            # NOTE: to consider: discard data with an old timestamp (define old)

            # Add to temporay DB for further processing
            self.ris_cache.sadd('for_ris_lookup', str(ip))
            pipeline = self.redis_sanitized.pipeline()
            pipeline.hmset(uuid, {'ip': str(ip), 'source': data['source'],
                                  'date': date, 'datetime': data['datetime']})
            pipeline.sadd('to_insert', uuid)
            pipeline.execute()
            self.redis_intake.delete(uuid)


class DatabaseInsert():

    def __init__(self, loglevel: int=logging.DEBUG):
        self.__init_logger(loglevel)
        self.ardb_storage = StrictRedis(host='localhost', port=16379, decode_responses=True)
        self.redis_sanitized = Redis(host='localhost', port=6380, db=0, decode_responses=True)
        self.ris_cache = Redis(host='localhost', port=6381, db=0, decode_responses=True)
        self.logger.debug('Starting import')

    def __init_logger(self, loglevel):
        self.logger = logging.getLogger('{}'.format(self.__class__.__name__))
        self.logger.setLevel(loglevel)

    async def insert(self):
        while True:
            uuid = self.redis_sanitized.spop('to_insert')
            if not uuid:
                break
            data = self.redis_sanitized.hgetall(uuid)
            # Data gathered from the RIS queries:
            # * IP Block of the IP -> https://stat.ripe.net/docs/data_api#NetworkInfo
            # * AS number -> https://stat.ripe.net/docs/data_api#NetworkInfo
            # * Full text description of the AS (older name) -> https://stat.ripe.net/docs/data_api#AsOverview
            ris_entry = self.ris_cache.hgetall(data['ip'])
            if not ris_entry:
                # RIS data not available yet, retry later
                # FIXME: an IP can sometimes not be announced, we need to discard it
                self.redis_sanitized.sadd('to_insert', uuid)
                # In case this IP is missing in the set to process
                self.ris_cache.sadd('for_ris_lookup', data['ip'])
                continue
            # Format: <YYYY-MM-DD>|sources -> set([<source>, ...])
            self.ardb_storage.sadd('{}|sources'.format(data['date']), data['source'])

            # Format: <YYYY-MM-DD>|<source> -> set([<asn>, ...])
            self.ardb_storage.sadd('{}|{}'.format(data['date'], data['source']),
                                   ris_entry['asn'])
            # Format: <YYYY-MM-DD>|<source>|<asn> -> set([<prefix>, ...])
            self.ardb_storage.sadd('{}|{}|{}'.format(data['date'], data['source'], ris_entry['asn']),
                                   ris_entry['prefix'])

            # Format: <YYYY-MM-DD>|<source>|<asn>|<prefix> -> set([<ip>|<datetime>, ...])
            self.ardb_storage.sadd('{}|{}|{}|{}'.format(data['date'], data['source'],
                                                        ris_entry['asn'],
                                                        ris_entry['prefix']),
                                   '{}|{}'.format(data['ip'], data['datetime']))
            self.redis_sanitized.delete(uuid)


class StatsRIPE():

    def __init__(self, sourceapp='bgpranking-ng - CIRCL'):
        self.url = "https://stat.ripe.net/data/{method}/data.json?{parameters}"
        self.url_parameters = {'sourceapp': sourceapp}

    async def network_info(self, ip: str) -> dict:
        method = 'network-info'
        self.url_parameters['resource'] = ip
        parameters = '&'.join(['='.join(item) for item in self.url_parameters.items()])
        url = self.url.format(method=method, parameters=parameters)
        response = requests.get(url)
        return response.json()

    async def prefix_overview(self, prefix: str) -> dict:
        method = 'prefix-overview'
        self.url_parameters['resource'] = prefix
        parameters = '&'.join(['='.join(item) for item in self.url_parameters.items()])
        url = self.url.format(method=method, parameters=parameters)
        response = requests.get(url)
        return response.json()


class RoutingInformationServiceFetcher():

    def __init__(self, loglevel: int=logging.DEBUG):
        self.__init_logger(loglevel)
        self.ris_cache = Redis(host='localhost', port=6381, db=0)
        self.logger.debug('Starting RIS fetcher')
        self.ripe = StatsRIPE()

    def __init_logger(self, loglevel):
        self.logger = logging.getLogger('{}'.format(self.__class__.__name__))
        self.logger.setLevel(loglevel)

    async def fetch(self):
        while True:
            ip = self.ris_cache.spop('for_ris_lookup')
            if not ip:
                break
            ip = ip.decode()
            network_info = await self.ripe.network_info(ip)
            prefix = network_info['data']['prefix']
            asns = network_info['data']['asns']
            if not asns or not prefix:
                self.logger.warning('The IP {} does not seem to be announced'.format(ip))
                continue
            prefix_overview = await self.ripe.prefix_overview(prefix)
            description = prefix_overview['data']['block']['desc']
            if not description:
                description = prefix_overview['data']['block']['name']
            for asn in asns:
                self.ris_cache.hmset(ip, {'asn': asn, 'prefix': prefix,
                                          'description': description})


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
        self.logger = logging.getLogger('{}-{}-{}'.format(self.__class__.__name__,
                                                          self.vendor, self.listname))
        self.logger.setLevel(loglevel)

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
