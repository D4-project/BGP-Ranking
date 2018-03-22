#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from redis import Redis

import time
import pytricia
import ipaddress


class RISPrefixLookup():

    def __init__(self, loglevel: int=logging.DEBUG):
        self.__init_logger(loglevel)
        self.logger.debug('Starting RIS Prefix fetcher')
        self.prefix_db = Redis(host='localhost', port=6582, db=0, decode_responses=True)
        self.longest_prefix_matching = Redis(host='localhost', port=6581, db=0, decode_responses=True)
        self.tree_v4 = pytricia.PyTricia()
        self.tree_v6 = pytricia.PyTricia(128)
        self.init_tree()

    def __init_logger(self, loglevel):
        self.logger = logging.getLogger('{}'.format(self.__class__.__name__))
        self.logger.setLevel(loglevel)

    def cache_prefix(self, ip, prefix, asns):
        p = self.longest_prefix_matching.pipeline()
        p.hmset(ip, {'asn': asns, 'prefix': prefix})
        p.expire(ip, 43200)  # 12H
        p.execute()

    def init_tree(self):
        for asn in self.prefix_db.smembers('asns'):
            for prefix in self.prefix_db.smembers('{}|{}'.format(asn, 'v4')):
                self.tree_v4[prefix] = asn
            for prefix in self.prefix_db.smembers('{}|{}'.format(asn, 'v6')):
                self.tree_v6[prefix] = asn

    def run(self):
        while True:
            ip = self.longest_prefix_matching.spop('for_ris_lookup')
            if not ip:  # TODO: add a check against something to stop the loop
                self.logger.debug('Nothing to lookup')
                time.sleep(10)
                continue
            if self.longest_prefix_matching.exists(ip):
                self.logger.debug('Already cached: {}'.format(ip))
                continue
            ip = ipaddress.ip_address(ip)
            if ip.version == 4:
                prefix = self.tree_v4.get_key(ip)
                asns = self.tree_v4.get(ip)
            else:
                prefix = self.tree_v6.get_key(ip)
                asns = self.tree_v6.get(ip)
            if not prefix:
                self.logger.warning('The IP {} does not seem to be announced'.format(ip))
                continue
            self.cache_prefix(ip, prefix, asns)
