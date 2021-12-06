#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json

from redis import Redis
from bgpranking.default import get_socket_path
from bgpranking.helpers import get_ipasn


class Monitor():

    def __init__(self):
        self.intake = Redis(unix_socket_path=get_socket_path('intake'), db=0, decode_responses=True)
        self.sanitize = Redis(unix_socket_path=get_socket_path('prepare'), db=0, decode_responses=True)
        self.cache = Redis(unix_socket_path=get_socket_path('cache'), db=1, decode_responses=True)
        self.ipasn = get_ipasn()

    def get_values(self):
        ips_in_intake = self.intake.scard('intake')
        ready_to_insert = self.sanitize.scard('to_insert')
        ipasn_meta = self.ipasn.meta()
        if len(ipasn_meta['cached_dates']['caida']['v4']['cached']) > 15:
            ipasn_meta['cached_dates']['caida']['v4']['cached'] = 'Too many entries'
        if len(ipasn_meta['cached_dates']['caida']['v6']['cached']) > 15:
            ipasn_meta['cached_dates']['caida']['v6']['cached'] = 'Too many entries'
        return json.dumps({'Non-parsed IPs': ips_in_intake, 'Parsed IPs': ready_to_insert,
                           'running': self.cache.zrangebyscore('running', '-inf', '+inf', withscores=True),
                           'IPASN History': ipasn_meta},
                          indent=2)


if __name__ == '__main__':
    m = Monitor()
    print(m.get_values())
