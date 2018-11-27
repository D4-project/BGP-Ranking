#!/usr/bin/env python
# -*- coding: utf-8 -*-

from datetime import timezone
from dateutil import parser
import logging
from redis import StrictRedis
import ipaddress

from .libs.helpers import shutdown_requested, set_running, unset_running, get_socket_path, get_ipasn, sanity_check_ipasn


class Sanitizer():

    def __init__(self, loglevel: int=logging.DEBUG):
        self.__init_logger(loglevel)
        self.redis_intake = StrictRedis(unix_socket_path=get_socket_path('intake'), db=0, decode_responses=True)
        self.redis_sanitized = StrictRedis(unix_socket_path=get_socket_path('prepare'), db=0, decode_responses=True)
        self.ipasn = get_ipasn()
        self.logger.debug('Starting import')

    def __init_logger(self, loglevel):
        self.logger = logging.getLogger(f'{self.__class__.__name__}')
        self.logger.setLevel(loglevel)

    def sanitize(self):
        ready, message = sanity_check_ipasn(self.ipasn)
        if not ready:
            # Try again later.
            self.logger.warning(message)
            return
        self.logger.debug(message)

        set_running(self.__class__.__name__)
        while True:
            if shutdown_requested():
                break
            uuids = self.redis_intake.spop('intake', 100)
            if not uuids:
                break
            for_cache = []
            pipeline = self.redis_sanitized.pipeline(transaction=False)
            for uuid in uuids:
                data = self.redis_intake.hgetall(uuid)
                try:
                    ip = ipaddress.ip_address(data['ip'])
                    if isinstance(ip, ipaddress.IPv6Address):
                        address_family = 'v6'
                    else:
                        address_family = 'v4'
                except ValueError:
                    self.logger.info(f"Invalid IP address: {data['ip']}")
                    continue
                if not ip.is_global:
                    self.logger.info(f"The IP address {data['ip']} is not global")
                    continue

                datetime = parser.parse(data['datetime'])
                if datetime.tzinfo:
                    # Make sure the datetime isn't TZ aware, and UTC.
                    datetime = datetime.astimezone(timezone.utc).replace(tzinfo=None)

                for_cache.append({'ip': str(ip), 'address_family': address_family, 'source': 'caida',
                                  'date': datetime.isoformat(), 'precision_delta': {'days': 3}})

                # Add to temporay DB for further processing
                pipeline.hmset(uuid, {'ip': str(ip), 'source': data['source'], 'address_family': address_family,
                                      'date': datetime.date().isoformat(), 'datetime': datetime.isoformat()})
                pipeline.sadd('to_insert', uuid)
            pipeline.execute()
            self.redis_intake.delete(*uuids)

            # Just cache everything so the lookup scripts can do their thing.
            self.ipasn.mass_cache(for_cache)
        unset_running(self.__class__.__name__)
