#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import datetime
from pathlib import Path
import logging
try:
    import simplejson as json
except ImportError:
    import json
import re
from redis import StrictRedis
from uuid import uuid4
from io import BytesIO
import importlib

from typing import List
import types

from .libs.helpers import safe_create_dir, set_running, unset_running, get_socket_path


class RawFilesParser():

    def __init__(self, config_file: Path, storage_directory: Path,
                 loglevel: int=logging.DEBUG) -> None:
        with open(config_file, 'r') as f:
            module_parameters = json.load(f)
        self.vendor = module_parameters['vendor']
        self.listname = module_parameters['name']
        if 'parser' in module_parameters:
            self.parse_raw_file = types.MethodType(importlib.import_module(module_parameters['parser'], 'bgpranking').parse_raw_file, self)
        self.source = f'{self.vendor}-{self.listname}'
        self.directory = storage_directory / self.vendor / self.listname
        safe_create_dir(self.directory)
        self.unparsable_dir = self.directory / 'unparsable'
        safe_create_dir(self.unparsable_dir)
        self.__init_logger(loglevel)
        self.redis_intake = StrictRedis(unix_socket_path=get_socket_path('intake'), db=0)
        self.logger.debug(f'Starting intake on {self.source}')

    def __init_logger(self, loglevel) -> None:
        self.logger = logging.getLogger(f'{self.__class__.__name__}-{self.vendor}-{self.listname}')
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

    def parse_raw_file(self, f: BytesIO) -> List[bytes]:
        # If the list doesn't provide a time, fallback to current day, midnight
        self.datetime = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.extract_ipv4(f.getvalue())

    def parse_raw_files(self) -> None:
        set_running(f'{self.__class__.__name__}-{self.source}')
        nb_unparsable_files = len([f for f in self.unparsable_dir.iterdir() if f.is_file()])
        if nb_unparsable_files:
            self.logger.warning(f'Was unable to parse {nb_unparsable_files} files.')
        try:
            for filepath in self.files_to_parse:
                self.logger.debug('Parsing {}, {} to go.'.format(filepath, len(self.files_to_parse) - 1))
                with open(filepath, 'rb') as f:
                    to_parse = BytesIO(f.read())
                p = self.redis_intake.pipeline()
                for ip in self.parse_raw_file(to_parse):
                    if isinstance(ip, tuple):
                        ip, datetime = ip
                    else:
                        datetime = self.datetime
                    uuid = uuid4()
                    p.hmset(str(uuid), {'ip': ip, 'source': self.source,
                                        'datetime': datetime.isoformat()})
                    p.sadd('intake', str(uuid))
                p.execute()
                self._archive(filepath)
        except Exception as e:
            self.logger.exception("That didn't go well")
            self._unparsable(filepath)
        finally:
            unset_running(f'{self.__class__.__name__}-{self.source}')

    def _archive(self, filepath: Path) -> None:
        '''After processing, move file to the archive directory'''
        filepath.rename(self.directory / 'archive' / filepath.name)

    def _unparsable(self, filepath: Path) -> None:
        '''After processing, move file to the archive directory'''
        filepath.rename(self.unparsable_dir / filepath.name)
