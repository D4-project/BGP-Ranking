#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from redis import StrictRedis

import time
import pytricia
import ipaddress
from .libs.helpers import shutdown_requested, set_running, unset_running, get_socket_path


class RISPrefixLookup():

    def __init__(self, loglevel: int=logging.DEBUG):
        self.__init_logger(loglevel)
        self.logger.info('Starting RIS Prefix fetcher')
        self.prefix_db = StrictRedis(unix_socket_path=get_socket_path('prefixes'), db=0, decode_responses=True)
        self.longest_prefix_matching = StrictRedis(unix_socket_path=get_socket_path('ris'), db=0, decode_responses=True)
        self.tree_v4 = pytricia.PyTricia()
        self.tree_v6 = pytricia.PyTricia(128)
        self.force_init = True
        self.current_v4 = None
        self.current_v6 = None

    def __init_logger(self, loglevel):
        self.logger = logging.getLogger(f'{self.__class__.__name__}')
        self.logger.setLevel(loglevel)

    def cache_prefix(self, pipe, ip, prefix, asns):
        pipe.hmset(ip, {'asn': asns, 'prefix': prefix})
        pipe.expire(ip, 43200)  # 12H

    def init_tree(self):
        for asn in self.prefix_db.smembers('asns'):
            for prefix in self.prefix_db.smembers(f'{asn}|v4'):
                self.tree_v4[prefix] = asn
            for prefix in self.prefix_db.smembers(f'{asn}|v6'):
                self.tree_v6[prefix] = asn
        self.tree_v4['0.0.0.0/0'] = 0
        self.tree_v6['::/0'] = 0
        self.current_v4 = self.prefix_db.get('current|v4')
        self.current_v6 = self.prefix_db.get('current|v6')

    def run(self):
        set_running(self.__class__.__name__)
        while True:
            if shutdown_requested():
                break
            if not self.prefix_db.get('ready'):
                self.logger.debug('Prefix database not ready.')
                time.sleep(5)
                self.force_init = True
                continue
            if (self.force_init or
                    (self.current_v4 != self.prefix_db.get('current|v4')) or
                    (self.current_v6 != self.prefix_db.get('current|v6'))):
                self.init_tree()
                self.force_init = False

            ips = self.longest_prefix_matching.spop('for_ris_lookup', 100)
            if not ips:  # TODO: add a check against something to stop the loop
                self.logger.debug('Nothing to lookup')
                break
            pipe = self.longest_prefix_matching.pipeline(transaction=False)
            for ip in ips:
                if self.longest_prefix_matching.exists(ip):
                    self.logger.debug(f'Already cached: {ip}')
                    continue
                ip = ipaddress.ip_address(ip)
                if ip.version == 4:
                    prefix = self.tree_v4.get_key(ip)
                    asns = self.tree_v4.get(ip)
                else:
                    prefix = self.tree_v6.get_key(ip)
                    asns = self.tree_v6.get(ip)
                if not prefix:
                    self.logger.warning(f'The IP {ip} does not seem to be announced')
                    continue
                self.cache_prefix(pipe, ip, prefix, asns)
            pipe.execute()
        unset_running(self.__class__.__name__)
