#!/usr/bin/env python
# -*- coding: utf-8 -*-

from dateutil import parser
import logging
from redis import StrictRedis
from .libs.helpers import shutdown_requested, set_running, unset_running, get_socket_path

import ipaddress


class Sanitizer():

    def __init__(self, loglevel: int=logging.DEBUG):
        self.__init_logger(loglevel)
        self.redis_intake = StrictRedis(unix_socket_path=get_socket_path('intake'), db=0, decode_responses=True)
        self.redis_sanitized = StrictRedis(unix_socket_path=get_socket_path('prepare'), db=0, decode_responses=True)
        self.ris_cache = StrictRedis(unix_socket_path=get_socket_path('ris'), db=0, decode_responses=True)
        self.logger.debug('Starting import')

    def __init_logger(self, loglevel):
        self.logger = logging.getLogger(f'{self.__class__.__name__}')
        self.logger.setLevel(loglevel)

    def sanitize(self):
        set_running(self.__class__.__name__)
        while True:
            if shutdown_requested():
                break
            uuids = self.redis_intake.spop('intake', 100)
            if not uuids:
                break
            for_ris_lookup = []
            pipeline = self.redis_sanitized.pipeline(transaction=False)
            for uuid in uuids:
                data = self.redis_intake.hgetall(uuid)
                try:
                    ip = ipaddress.ip_address(data['ip'])
                except ValueError:
                    self.logger.info(f"Invalid IP address: {data['ip']}")
                    continue
                if not ip.is_global:
                    self.logger.info(f"The IP address {data['ip']} is not global")
                    continue

                date = parser.parse(data['datetime']).date().isoformat()
                # NOTE: to consider: discard data with an old timestamp (define old)

                # Add to temporay DB for further processing
                for_ris_lookup.append(str(ip))
                pipeline.hmset(uuid, {'ip': str(ip), 'source': data['source'],
                                      'date': date, 'datetime': data['datetime']})
                pipeline.sadd('to_insert', uuid)
            pipeline.execute()
            self.redis_intake.delete(*uuids)
            self.ris_cache.sadd('for_ris_lookup', *for_ris_lookup)
        unset_running(self.__class__.__name__)
