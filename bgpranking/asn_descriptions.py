#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from pathlib import Path
import requests
from redis import StrictRedis
from dateutil.parser import parse
import re

from .libs.helpers import set_running, unset_running, get_socket_path, safe_create_dir


class ASNDescriptions():

    def __init__(self, storage_directory: Path, loglevel: int=logging.DEBUG):
        self.__init_logger(loglevel)
        self.asn_meta = StrictRedis(unix_socket_path=get_socket_path('storage'), db=2, decode_responses=True)
        self.logger.debug('Starting ASN History')
        self.directory = storage_directory / 'ans_descriptions'
        safe_create_dir(self.directory)
        self.archives = self.directory / 'archive'
        safe_create_dir(self.archives)
        self.url = 'http://www.cidr-report.org/as2.0/autnums.html'

    def __init_logger(self, loglevel):
        self.logger = logging.getLogger(f'{self.__class__.__name__}')
        self.logger.setLevel(loglevel)

    def __update_available(self):
        r = requests.head(self.url)
        current_last_modified = parse(r.headers['Last-Modified'])
        if not self.asn_meta.exists('ans_description_last_update'):
            return True
        last_update = parse(self.asn_meta.get('ans_description_last_update'))
        if last_update < current_last_modified:
            return True
        return False

    def load_descriptions(self):
        if not self.__update_available():
            self.logger.debug('No new file to import.')
            return
        set_running(self.__class__.__name__)
        self.logger.info('Importing new ASN descriptions.')
        r = requests.get(self.url)
        last_modified = parse(r.headers['Last-Modified']).isoformat()
        p = self.asn_meta.pipeline()
        new_asn = 0
        new_description = 0
        for asn, descr in re.findall('as=AS(.*)&.*</a> (.*)\n', r.text):
            existing_descriptions = self.asn_meta.hgetall(f'{asn}|descriptions')
            if not existing_descriptions:
                self.logger.debug(f'New ASN: {asn} - {descr}')
                p.hset(f'{asn}|descriptions', last_modified, descr)
                new_asn += 1
            else:
                last_descr = sorted(existing_descriptions.keys(), reverse=True)[0]
                if descr != existing_descriptions[last_descr]:
                    self.logger.debug(f'New description for {asn}: {existing_descriptions[last_descr]} -> {descr}')
                    p.hset(f'{asn}|descriptions', last_modified, descr)
                    new_description += 1
        p.set('ans_description_last_update', last_modified)
        p.execute()
        self.logger.info(f'Done with import. New ASNs: {new_asn}, new descriptions: {new_description}')
        unset_running(self.__class__.__name__)
