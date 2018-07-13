#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from redis import StrictRedis
from .libs.helpers import set_running, unset_running, get_socket_path, load_config_files
from datetime import datetime, date, timedelta
from ipaddress import ip_network
from pathlib import Path


class Ranking():

    def __init__(self, config_dir: Path=None, loglevel: int=logging.DEBUG):
        self.__init_logger(loglevel)
        self.storage = StrictRedis(unix_socket_path=get_socket_path('storage'), decode_responses=True)
        self.ranking = StrictRedis(unix_socket_path=get_socket_path('storage'), db=1, decode_responses=True)
        self.asn_meta = StrictRedis(unix_socket_path=get_socket_path('storage'), db=2, decode_responses=True)
        self.config_files = load_config_files(config_dir)

    def __init_logger(self, loglevel):
        self.logger = logging.getLogger(f'{self.__class__.__name__}')
        self.logger.setLevel(loglevel)

    def rank_a_day(self, day: str):
        # FIXME: If we want to rank an older date, we need to hav older datasets for the announces
        v4_last, v6_last = self.asn_meta.mget('v4|last', 'v6|last')
        asns_aggregation_key_v4 = f'{day}|asns|v4'
        asns_aggregation_key_v6 = f'{day}|asns|v6'
        to_delete = set([asns_aggregation_key_v4, asns_aggregation_key_v6])
        r_pipeline = self.ranking.pipeline()
        for source in self.storage.smembers(f'{day}|sources'):
            self.logger.info(f'{day} - Ranking source: {source}')
            source_aggregation_key_v4 = f'{day}|{source}|asns|v4'
            source_aggregation_key_v6 = f'{day}|{source}|asns|v6'
            to_delete.update([source_aggregation_key_v4, source_aggregation_key_v6])
            for asn in self.storage.smembers(f'{day}|{source}'):
                prefixes_aggregation_key_v4 = f'{day}|{asn}|v4'
                prefixes_aggregation_key_v6 = f'{day}|{asn}|v6'
                to_delete.update([prefixes_aggregation_key_v4, prefixes_aggregation_key_v6])
                if asn == '0':
                    # Default ASN when no matches. Probably spoofed.
                    continue
                self.logger.debug(f'{day} - Ranking source: {source} / ASN: {asn}')
                asn_rank_v4 = 0.0
                asn_rank_v6 = 0.0
                for prefix in self.storage.smembers(f'{day}|{source}|{asn}'):
                    ips = set([ip_ts.split('|')[0]
                               for ip_ts in self.storage.smembers(f'{day}|{source}|{asn}|{prefix}')])
                    py_prefix = ip_network(prefix)
                    prefix_rank = float(len(ips)) / py_prefix.num_addresses
                    r_pipeline.zadd(f'{day}|{source}|{asn}|v{py_prefix.version}|prefixes', prefix_rank, prefix)
                    if py_prefix.version == 4:
                        asn_rank_v4 += len(ips) * self.config_files[source]['impact']
                        r_pipeline.zincrby(prefixes_aggregation_key_v4, prefix, prefix_rank * self.config_files[source]['impact'])
                    else:
                        asn_rank_v6 += len(ips) * self.config_files[source]['impact']
                        r_pipeline.zincrby(prefixes_aggregation_key_v6, prefix, prefix_rank * self.config_files[source]['impact'])
                v4count, v6count = self.asn_meta.mget(f'{v4_last}|{asn}|v4|ipcount', f'{v6_last}|{asn}|v6|ipcount')
                if v4count:
                    asn_rank_v4 /= float(v4count)
                    if asn_rank_v4:
                        r_pipeline.set(f'{day}|{source}|{asn}|v4', asn_rank_v4)
                        r_pipeline.zincrby(asns_aggregation_key_v4, asn, asn_rank_v4)
                        r_pipeline.zadd(source_aggregation_key_v4, asn_rank_v4, asn)
                if v6count:
                    asn_rank_v6 /= float(v6count)
                    if asn_rank_v6:
                        r_pipeline.set(f'{day}|{source}|{asn}|v6', asn_rank_v6)
                        r_pipeline.zincrby(asns_aggregation_key_v6, asn, asn_rank_v6)
                        r_pipeline.zadd(source_aggregation_key_v6, asn_rank_v4, asn)
        self.ranking.delete(*to_delete)
        r_pipeline.execute()

    def compute(self):
        self.logger.info('Start ranking')
        set_running(self.__class__.__name__)
        if self.asn_meta.exists('v4|last', 'v6|last') != 2:
            '''Failsafe if asn_meta has not been populated yet'''
            unset_running(self.__class__.__name__)
            return
        today = date.today()
        now = datetime.now()
        today12am = now.replace(hour=12, minute=0, second=0, microsecond=0)
        if now < today12am:
            # Compute yesterday and today's ranking (useful when we have lists generated only once a day)
            self.rank_a_day((today - timedelta(days=1)).isoformat())
        self.rank_a_day(today.isoformat())
        unset_running(self.__class__.__name__)
        self.logger.info('Ranking done.')
