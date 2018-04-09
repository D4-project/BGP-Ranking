#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from redis import StrictRedis
from .libs.helpers import shutdown_requested, set_running, unset_running, get_socket_path


class DatabaseInsert():

    def __init__(self, loglevel: int=logging.DEBUG):
        self.__init_logger(loglevel)
        self.ardb_storage = StrictRedis(unix_socket_path=get_socket_path('storage'), decode_responses=True)
        self.redis_sanitized = StrictRedis(unix_socket_path=get_socket_path('prepare'), db=0, decode_responses=True)
        self.ris_cache = StrictRedis(unix_socket_path=get_socket_path('ris'), db=0, decode_responses=True)
        self.logger.debug('Starting import')

    def __init_logger(self, loglevel):
        self.logger = logging.getLogger(f'{self.__class__.__name__}')
        self.logger.setLevel(loglevel)

    def insert(self):
        set_running(self.__class__.__name__)
        while True:
            if shutdown_requested():
                break
            uuids = self.redis_sanitized.spop('to_insert', 1000)
            if not uuids:
                break
            p = self.redis_sanitized.pipeline(transaction=False)
            [p.hgetall(uuid) for uuid in uuids]
            sanitized_data = p.execute()

            retry = []
            done = []
            prefix_missing = []
            ardb_pipeline = self.ardb_storage.pipeline(transaction=False)
            for i, uuid in enumerate(uuids):
                data = sanitized_data[i]
                if not data:
                    self.logger.warning(f'No data for UUID {uuid}. This should not happen, but lets move on.')
                    continue
                # Data gathered from the RIS queries:
                # * IP Block of the IP -> https://stat.ripe.net/docs/data_api#NetworkInfo
                # * AS number -> https://stat.ripe.net/docs/data_api#NetworkInfo
                # * Full text description of the AS (older name) -> https://stat.ripe.net/docs/data_api#AsOverview
                ris_entry = self.ris_cache.hgetall(data['ip'])
                if not ris_entry:
                    # RIS data not available yet, retry later
                    retry.append(uuid)
                    # In case this IP is missing in the set to process
                    prefix_missing.append(data['ip'])
                    continue
                # Format: <YYYY-MM-DD>|sources -> set([<source>, ...])
                ardb_pipeline.sadd(f"{data['date']}|sources", data['source'])

                # Format: <YYYY-MM-DD>|<source> -> set([<asn>, ...])
                ardb_pipeline.sadd(f"{data['date']}|{data['source']}", ris_entry['asn'])
                # Format: <YYYY-MM-DD>|<source>|<asn> -> set([<prefix>, ...])
                ardb_pipeline.sadd(f"{data['date']}|{data['source']}|{ris_entry['asn']}", ris_entry['prefix'])

                # Format: <YYYY-MM-DD>|<source>|<asn>|<prefix> -> set([<ip>|<datetime>, ...])
                ardb_pipeline.sadd(f"{data['date']}|{data['source']}|{ris_entry['asn']}|{ris_entry['prefix']}",
                                   f"{data['ip']}|{data['datetime']}")
                done.append(uuid)
            ardb_pipeline.execute()
            if prefix_missing:
                self.ris_cache.sadd('for_ris_lookup', *prefix_missing)
            p = self.redis_sanitized.pipeline(transaction=False)
            if done:
                p.delete(*done)
            if retry:
                p.sadd('to_insert', *retry)
            p.execute()
        unset_running(self.__class__.__name__)
