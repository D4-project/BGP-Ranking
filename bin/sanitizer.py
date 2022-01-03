#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import ipaddress
import logging
import time

from datetime import timezone
from typing import Optional, List, Dict

from dateutil import parser
from redis import Redis
import requests

from bgpranking.default import AbstractManager, get_socket_path
from bgpranking.helpers import get_ipasn, sanity_check_ipasn

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO)


class Sanitizer(AbstractManager):

    def __init__(self, loglevel: int=logging.INFO):
        super().__init__(loglevel)
        self.script_name = 'sanitizer'
        self.redis_intake = Redis(unix_socket_path=get_socket_path('intake'), db=0, decode_responses=True)
        self.redis_sanitized = Redis(unix_socket_path=get_socket_path('prepare'), db=0, decode_responses=True)
        self.ipasn = get_ipasn()
        self.logger.debug('Starting import')

    def _sanitize_ip(self, pipeline: Redis, uuid: str, data: Dict) -> Optional[Dict]:
        try:
            ip = ipaddress.ip_address(data['ip'])
            if isinstance(ip, ipaddress.IPv6Address):
                address_family = 'v6'
            else:
                address_family = 'v4'
        except ValueError:
            self.logger.info(f"Invalid IP address: {data['ip']}")
            return None
        except KeyError:
            self.logger.info(f"Invalid entry {data}")
            return None

        if not ip.is_global:
            self.logger.info(f"The IP address {data['ip']} is not global")
            return None

        datetime = parser.parse(data['datetime'])
        if datetime.tzinfo:
            # Make sure the datetime isn't TZ aware, and UTC.
            datetime = datetime.astimezone(timezone.utc).replace(tzinfo=None)

        # Add to temporay DB for further processing
        pipeline.hmset(uuid, {'ip': str(ip), 'source': data['source'], 'address_family': address_family,
                              'date': datetime.date().isoformat(), 'datetime': datetime.isoformat()})
        pipeline.sadd('to_insert', uuid)

        return {'ip': str(ip), 'address_family': address_family, 'source': 'caida',
                'date': datetime.isoformat(), 'precision_delta': {'days': 3}}

    def _sanitize_network(self, pipeline: Redis, uuid: str, data: Dict) -> List[Dict]:
        try:
            network = ipaddress.ip_network(data['ip'])
            if isinstance(network, ipaddress.IPv6Network):
                address_family = 'v6'
            else:
                address_family = 'v4'
        except ValueError:
            self.logger.info(f"Invalid IP network: {data['ip']}")
            return []
        except KeyError:
            self.logger.info(f"Invalid entry {data}")
            return []

        datetime = parser.parse(data['datetime'])
        if datetime.tzinfo:
            # Make sure the datetime isn't TZ aware, and UTC.
            datetime = datetime.astimezone(timezone.utc).replace(tzinfo=None)

        for_cache = []
        for ip in network.hosts():
            if not ip.is_global:
                self.logger.info(f"The IP address {ip} is not global")
                continue

            # Add to temporay DB for further processing
            pipeline.hmset(uuid, {'ip': str(ip), 'source': data['source'], 'address_family': address_family,
                                  'date': datetime.date().isoformat(), 'datetime': datetime.isoformat()})
            pipeline.sadd('to_insert', uuid)

            for_cache.append({'ip': str(ip), 'address_family': address_family, 'source': 'caida',
                              'date': datetime.isoformat(), 'precision_delta': {'days': 3}})
        return for_cache

    def sanitize(self):
        ready, message = sanity_check_ipasn(self.ipasn)
        if not ready:
            # Try again later.
            self.logger.warning(message)
            return
        self.logger.debug(message)

        while True:
            try:
                if self.shutdown_requested() or not self.ipasn.is_up:
                    break
            except requests.exceptions.ConnectionError:
                # Temporary issue with ipasnhistory
                self.logger.info('Temporary issue with ipasnhistory, trying again later.')
                time.sleep(10)
                continue
            uuids: Optional[List[str]] = self.redis_intake.spop('intake', 100)  # type: ignore
            if not uuids:
                break
            for_cache = []
            pipeline = self.redis_sanitized.pipeline(transaction=False)
            for uuid in uuids:
                data = self.redis_intake.hgetall(uuid)
                if not data:
                    continue
                if '/' in data['ip']:
                    entries_for_cache = self._sanitize_network(pipeline, uuid, data)
                    if entries_for_cache:
                        for_cache += entries_for_cache
                else:
                    entry_for_cache = self._sanitize_ip(pipeline, uuid, data)
                    if entry_for_cache:
                        for_cache.append(entry_for_cache)

            pipeline.execute()
            self.redis_intake.delete(*uuids)

            try:
                # Just cache everything so the lookup scripts can do their thing.
                self.ipasn.mass_cache(for_cache)
            except Exception:
                self.logger.info('Mass cache in IPASN History failed, trying again later.')
                # Rollback the spop
                self.redis_intake.sadd('intake', *uuids)
                break

    def _to_run_forever(self):
        self.sanitize()


def main():
    sanitizer = Sanitizer()
    sanitizer.run(sleep_in_sec=120)


if __name__ == '__main__':
    main()
