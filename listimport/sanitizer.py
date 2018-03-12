#!/usr/bin/env python
# -*- coding: utf-8 -*-

from dateutil import parser
import logging
from redis import Redis

import ipaddress


class Sanitizer():

    def __init__(self, loglevel: int=logging.DEBUG):
        self.__init_logger(loglevel)
        self.redis_intake = Redis(host='localhost', port=6379, db=0, decode_responses=True)
        self.redis_sanitized = Redis(host='localhost', port=6380, db=0, decode_responses=True)
        self.ris_cache = Redis(host='localhost', port=6381, db=0, decode_responses=True)
        self.logger.debug('Starting import')

    def __init_logger(self, loglevel):
        self.logger = logging.getLogger('{}'.format(self.__class__.__name__))
        self.logger.setLevel(loglevel)

    async def sanitize(self):
        while True:
            uuid = self.redis_intake.spop('intake')
            if not uuid:
                break
            data = self.redis_intake.hgetall(uuid)
            try:
                ip = ipaddress.ip_address(data['ip'])
            except ValueError:
                self.logger.info('Invalid IP address: {}'.format(data['ip']))
                continue
            if not ip.is_global:
                self.logger.info('The IP address {} is not global'.format(data['ip']))
                continue

            date = parser.parse(data['datetime']).date().isoformat()
            # NOTE: to consider: discard data with an old timestamp (define old)

            # Add to temporay DB for further processing
            self.ris_cache.sadd('for_ris_lookup', str(ip))
            pipeline = self.redis_sanitized.pipeline()
            pipeline.hmset(uuid, {'ip': str(ip), 'source': data['source'],
                                  'date': date, 'datetime': data['datetime']})
            pipeline.sadd('to_insert', uuid)
            pipeline.execute()
            self.redis_intake.delete(uuid)
