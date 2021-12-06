#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import importlib
import json
import logging
import re
import types

from datetime import datetime
from io import BytesIO
from logging import Logger
from pathlib import Path
from typing import List, Union, Tuple
from uuid import uuid4

from redis import Redis

from bgpranking.default import AbstractManager, safe_create_dir, get_socket_path
from bgpranking.helpers import get_modules, get_data_dir, get_modules_dir


logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')


class RawFilesParser():

    def __init__(self, config_file: Path, logger: Logger) -> None:
        self.logger = logger
        with open(config_file, 'r') as f:
            module_parameters = json.load(f)
        self.vendor = module_parameters['vendor']
        self.listname = module_parameters['name']
        if 'parser' in module_parameters:
            self.parse_raw_file = types.MethodType(importlib.import_module(module_parameters['parser'], 'bgpranking').parse_raw_file, self)  # type: ignore
        self.source = f'{self.vendor}-{self.listname}'
        self.directory = get_data_dir() / self.vendor / self.listname
        safe_create_dir(self.directory)
        self.unparsable_dir = self.directory / 'unparsable'
        safe_create_dir(self.unparsable_dir)
        self.redis_intake = Redis(unix_socket_path=get_socket_path('intake'), db=0)
        self.logger.debug(f'{self.source}: Starting intake.')

    @property
    def files_to_parse(self) -> List[Path]:
        return sorted([f for f in self.directory.iterdir() if f.is_file()], reverse=True)

    def extract_ipv4(self, bytestream: bytes) -> List[Union[bytes, Tuple[bytes, datetime]]]:
        return re.findall(rb'[0-9]+(?:\.[0-9]+){3}', bytestream)

    def strip_leading_zeros(self, ips: List[bytes]) -> List[bytes]:
        '''Helper to get rid of leading 0s in an IP list.
        Only run it when needed, it is nasty and slow'''
        return ['.'.join(str(int(part)) for part in ip.split(b'.')).encode() for ip in ips]

    def parse_raw_file(self, f: BytesIO) -> List[Union[bytes, Tuple[bytes, datetime]]]:
        # If the list doesn't provide a time, fallback to current day, midnight
        self.datetime = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.extract_ipv4(f.getvalue())

    def parse_raw_files(self) -> None:
        nb_unparsable_files = len([f for f in self.unparsable_dir.iterdir() if f.is_file()])
        if nb_unparsable_files:
            self.logger.warning(f'{self.source}: Was unable to parse {nb_unparsable_files} files.')
        try:
            for filepath in self.files_to_parse:
                self.logger.debug(f'{self.source}: Parsing {filepath}, {len(self.files_to_parse) - 1} to go.')
                with open(filepath, 'rb') as f:
                    to_parse = BytesIO(f.read())
                p = self.redis_intake.pipeline()
                for line in self.parse_raw_file(to_parse):
                    if isinstance(line, tuple):
                        ip, datetime = line
                    else:
                        ip = line
                        datetime = self.datetime
                    uuid = uuid4()
                    p.hmset(str(uuid), {'ip': ip, 'source': self.source,
                                        'datetime': datetime.isoformat()})
                    p.sadd('intake', str(uuid))
                p.execute()
                self._archive(filepath)
        except Exception as e:
            self.logger.warning(f"{self.source}: That didn't go well: {e}")
            self._unparsable(filepath)

    def _archive(self, filepath: Path) -> None:
        '''After processing, move file to the archive directory'''
        filepath.rename(self.directory / 'archive' / filepath.name)

    def _unparsable(self, filepath: Path) -> None:
        '''After processing, move file to the archive directory'''
        filepath.rename(self.unparsable_dir / filepath.name)


class ParserManager(AbstractManager):

    def __init__(self, loglevel: int=logging.DEBUG):
        super().__init__(loglevel)
        self.script_name = 'parser'
        self.modules_paths = get_modules()
        self.modules = [RawFilesParser(path, self.logger) for path in self.modules_paths]

    def _to_run_forever(self):
        # Check if there are new config files
        new_modules_paths = [modulepath for modulepath in get_modules_dir().glob('*.json') if modulepath not in self.modules_paths]
        self.modules += [RawFilesParser(path, self.logger) for path in new_modules_paths]
        self.modules_paths += new_modules_paths

        if self.modules:
            for module in self.modules:
                module.parse_raw_files()
        else:
            self.logger.warning('No config files were found so there are no parsers running yet. Will try again later.')


def main():
    parser_manager = ParserManager()
    parser_manager.run(sleep_in_sec=120)


if __name__ == '__main__':
    main()
