#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from redis import Redis
from redis import StrictRedis
from .libs.helpers import shutdown_requested, set_running, unset_running


class DatabaseInsert():

    def __init__(self, loglevel: int=logging.DEBUG):
        self.__init_logger(loglevel)
        self.ardb_storage = StrictRedis(host='localhost', port=16579, decode_responses=True)
        self.redis_sanitized = Redis(host='localhost', port=6580, db=0, decode_responses=True)
        self.ris_cache = Redis(host='localhost', port=6581, db=0, decode_responses=True)
        self.logger.debug('Starting import')

    def __init_logger(self, loglevel):
        self.logger = logging.getLogger('{}'.format(self.__class__.__name__))
        self.logger.setLevel(loglevel)

    def insert(self):
        set_running(self.__class__.__name__)
        while True:
            if shutdown_requested():
                break
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
        unset_running(self.__class__.__name__)
