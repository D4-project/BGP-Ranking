#!/usr/bin/env python
# -*- coding: utf-8 -*-

from redis import StrictRedis
from .libs.helpers import get_socket_path


class Monitor():

    def __init__(self):
        self.intake = StrictRedis(unix_socket_path=get_socket_path('intake'), db=0, decode_responses=True)
        self.sanitize = StrictRedis(unix_socket_path=get_socket_path('prepare'), db=0, decode_responses=True)
        self.ris_cache = StrictRedis(unix_socket_path=get_socket_path('ris'), db=0, decode_responses=True)
        self.prefix_cache = StrictRedis(unix_socket_path=get_socket_path('prefixes'), db=0, decode_responses=True)
        self.running = StrictRedis(unix_socket_path=get_socket_path('prefixes'), db=1, decode_responses=True)
        self.storage = StrictRedis(unix_socket_path=get_socket_path('storage'), decode_responses=True)

    def get_runinng(self):
        return self.running.hgetall('running')

    def info_prefix_cache(self):
        to_return = {'IPv6 Dump': '', 'IPv4 Dump': '', 'Number ASNs': 0}
        if self.prefix_cache.exists('ready'):
            v6_dump = self.prefix_cache.get('current|v6')
            v4_dump = self.prefix_cache.get('current|v4')
            number_as = self.prefix_cache.scard('asns')
            to_return['IPv6 Dump'] = v6_dump
            to_return['IPv4 Dump'] = v4_dump
            to_return['Number ASNs'] = number_as
        return to_return

    def get_values(self):
        ips_in_intake = self.intake.scard('intake')
        waiting_for_ris_lookup = self.ris_cache.scard('for_ris_lookup')
        ready_to_insert = self.sanitize.scard('to_insert')
        prefix_db_ready = self.prefix_cache.exists('ready')
        return {'Non-parsed IPs': ips_in_intake, 'Parsed IPs': ready_to_insert,
                'Awaiting prefix lookup': waiting_for_ris_lookup,
                'Prefix database ready': prefix_db_ready}
