#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json

from redis import StrictRedis
from .libs.helpers import get_socket_path, get_ipasn


class Monitor():

    def __init__(self):
        self.intake = StrictRedis(unix_socket_path=get_socket_path('intake'), db=0, decode_responses=True)
        self.sanitize = StrictRedis(unix_socket_path=get_socket_path('prepare'), db=0, decode_responses=True)
        self.cache = StrictRedis(unix_socket_path=get_socket_path('cache'), db=1, decode_responses=True)
        self.ipasn = get_ipasn()

    def get_values(self):
        ips_in_intake = self.intake.scard('intake')
        ready_to_insert = self.sanitize.scard('to_insert')
        return json.dumps({'Non-parsed IPs': ips_in_intake, 'Parsed IPs': ready_to_insert,
                           'IPASN History': self.ipasn.meta(), 'running': self.cache.hgetall('running')},
                          indent=2)
