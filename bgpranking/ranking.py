#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from redis import StrictRedis
from .libs.helpers import set_running, unset_running, get_socket_path, load_config_files
from datetime import date
from ipaddress import ip_network
from pathlib import Path


class Ranking():

    def __init__(self, config_dir: Path=None, loglevel: int=logging.DEBUG):
        self.__init_logger(loglevel)
        self.storage = StrictRedis(unix_socket_path=get_socket_path('storage'), decode_responses=True)
        self.ranking = StrictRedis(unix_socket_path=get_socket_path('storage'), db=1, decode_responses=True)
        self.asn_meta = StrictRedis(unix_socket_path=get_socket_path('storage'), db=2, decode_responses=True)
        self.prefix_cache = StrictRedis(unix_socket_path=get_socket_path('prefixes'), db=0, decode_responses=True)
        self.config_files = load_config_files(config_dir)

    def __init_logger(self, loglevel):
        self.logger = logging.getLogger(f'{self.__class__.__name__}')
        self.logger.setLevel(loglevel)

    def compute(self):
        self.logger.info('Start ranking')
        set_running(self.__class__.__name__)
        today = date.today().isoformat()
        v4_last = self.asn_meta.get('v4|last')
        v6_last = self.asn_meta.get('v6|last')
        if not v4_last or not v6_last:
            '''Failsafe if asn_meta has not been populated yet'''
            return
        for source in self.ardb_storage.smembers(f'{today}|sources'):
            self.logger.info(f'{today} - Ranking source: {source}')
            r_pipeline = self.ranking.pipeline()
            for asn in self.ardb_storage.smembers(f'{today}|{source}'):
                self.logger.debug(f'{today} - Ranking source: {source} / ASN: {asn}')
                asn_rank_v4 = 0.0
                asn_rank_v6 = 0.0
                for prefix in self.ardb_storage.smembers(f'{today}|{source}|{asn}'):
                    ips = set([ip_ts.split('|')[0]
                               for ip_ts in self.ardb_storage.smembers(f'{today}|{source}|{asn}|{prefix}')])
                    prefix_rank = float(len(ips)) / ip_network(prefix).num_addresses
                    r_pipeline.zadd(f'{today}|{source}|{asn}|rankv{prefix_rank.version}|prefixes', prefix, prefix_rank)
                    if prefix_rank.version == 4:
                        asn_rank_v4 += len(ips) * self.config_files[source]['impact']
                    else:
                        asn_rank_v6 += len(ips) * self.config_files[source]['impact']
                asn_rank_v4 /= int(self.asn_meta.get(f'{v4_last}|{asn}|v4|ipcount'))
                asn_rank_v6 /= int(self.asn_meta.get(f'{v6_last}|{asn}|v6|ipcount'))
                if asn_rank_v4:
                    r_pipeline.set(f'{today}|{source}|{asn}|rankv4', asn_rank_v4)
                if asn_rank_v6:
                    r_pipeline.set(f'{today}|{source}|{asn}|rankv6', asn_rank_v6)
            r_pipeline.execute()
        unset_running(self.__class__.__name__)
        self.logger.info('Ranking done.')
