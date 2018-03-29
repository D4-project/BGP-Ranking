#!/usr/bin/env python
# -*- coding: utf-8 -*-

from dateutil import parser
import logging
from redis import StrictRedis
from .libs.helpers import shutdown_requested, set_running, unset_running

import ipaddress


class Sanitizer():

    def __init__(self, loglevel: int=logging.DEBUG):
        self.__init_logger(loglevel)
        self.redis_intake = StrictRedis(host='localhost', port=6579, db=0, decode_responses=True)
        self.redis_sanitized = StrictRedis(host='localhost', port=6580, db=0, decode_responses=True)
        self.ris_cache = StrictRedis(host='localhost', port=6581, db=0, decode_responses=True)
        self.logger.debug('Starting import')

    def __init_logger(self, loglevel):
        self.logger = logging.getLogger('{}'.format(self.__class__.__name__))
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
                    self.logger.info('Invalid IP address: {}'.format(data['ip']))
                    continue
                if not ip.is_global:
                    self.logger.info('The IP address {} is not global'.format(data['ip']))
                    continue

                date = parser.parse(data['datetime']).date().isoformat()
                # NOTE: to consider: discard data with an old timestamp (define old)

                # Add to temporay DB for further processing
                for_ris_lookup.append(str(ip))
                pipeline.hmset(uuid, {'ip': str(ip), 'source': data['source'],
                                      'date': date, 'datetime': data['datetime']})
                pipeline.sadd('to_insert', uuid)
            pipeline.execute()
            self.redis_intake.delete(*uuid)
            self.ris_cache.sadd('for_ris_lookup', *for_ris_lookup)
        unset_running(self.__class__.__name__)
