#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime
from pathlib import Path
import logging
import json
import re
from redis import Redis
from uuid import uuid4
from io import BytesIO
import importlib

from typing import List
import types

from .libs.helpers import safe_create_dir


class RawFilesParser():

    def __init__(self, config_file: Path, storage_directory: Path,
                 loglevel: int=logging.DEBUG):
        with open(config_file, 'r') as f:
            module_parameters = json.load(f)
        self.vendor = module_parameters['vendor']
        self.listname = module_parameters['name']
        if 'parser' in module_parameters:
            self.parse_raw_file = types.MethodType(importlib.import_module(module_parameters['parser'], 'listimport').parse_raw_file, self)
        self.source = '{}-{}'.format(self.vendor, self.listname)
        self.directory = storage_directory / self.vendor / self.listname
        safe_create_dir(self.directory)
        self.__init_logger(loglevel)
        self.redis_intake = Redis(host='localhost', port=6579, db=0)
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

    def strip_leading_zeros(self, ips: List[bytes]) -> List[bytes]:
        '''Helper to get rid of leading 0s in an IP list.
        Only run it when needed, it is nasty and slow'''
        return ['.'.join(str(int(part)) for part in ip.split(b'.')).encode() for ip in ips]

    def parse_raw_file(self, f: BytesIO):
        self.datetime = datetime.now()
        return self.extract_ipv4(f.getvalue())

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
