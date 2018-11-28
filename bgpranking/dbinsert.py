#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from redis import StrictRedis
from .libs.helpers import shutdown_requested, set_running, unset_running, get_socket_path, get_ipasn, sanity_check_ipasn


class DatabaseInsert():

    def __init__(self, loglevel: int=logging.DEBUG):
        self.__init_logger(loglevel)
        self.ardb_storage = StrictRedis(unix_socket_path=get_socket_path('storage'), decode_responses=True)
        self.redis_sanitized = StrictRedis(unix_socket_path=get_socket_path('prepare'), db=0, decode_responses=True)
        self.ipasn = get_ipasn()
        self.logger.debug('Starting import')

    def __init_logger(self, loglevel):
        self.logger = logging.getLogger(f'{self.__class__.__name__}')
        self.logger.setLevel(loglevel)

    def insert(self):
        ready, message = sanity_check_ipasn(self.ipasn)
        if not ready:
            # Try again later.
            self.logger.warning(message)
            return
        self.logger.debug(message)

        set_running(self.__class__.__name__)
        while True:
            if shutdown_requested() or not self.ipasn.is_up:
                break
            uuids = self.redis_sanitized.spop('to_insert', 100)
            if not uuids:
                break
            p = self.redis_sanitized.pipeline(transaction=False)
            [p.hgetall(uuid) for uuid in uuids]
            sanitized_data = p.execute()

            for_query = []
            for i, uuid in enumerate(uuids):
                data = sanitized_data[i]
                if not data:
                    self.logger.warning(f'No data for UUID {uuid}. This should not happen, but lets move on.')
                    continue
                for_query.append({'ip': data['ip'], 'address_family': data['address_family'], 'source': 'caida',
                                  'date': data['datetime'], 'precision_delta': {'days': 3}})
            try:
                responses = self.ipasn.mass_query(for_query)
            except Exception:
                self.logger.exception('Mass query in IPASN History failed, trying again later.')
                # Rollback the spop
                self.redis_sanitized.sadd('to_insert', *uuids)
                break
            retry = []
            done = []
            ardb_pipeline = self.ardb_storage.pipeline(transaction=False)
            for i, uuid in enumerate(uuids):
                data = sanitized_data[i]
                if not data:
                    self.logger.warning(f'No data for UUID {uuid}. This should not happen, but lets move on.')
                    continue
                routing_info = responses['responses'][i][0]  # our queries are on one single date, not a range
                # Data gathered from IPASN History:
                # * IP Block of the IP
                # * AS number
                if 'error' in routing_info:
                    self.logger.warning(f"Unable to find routing information for {data['ip']} - {data['datetime']}: {routing_info['error']}")
                    continue
                # Single date query, getting from the object
                datetime_routing = list(routing_info.keys())[0]
                entry = routing_info[datetime_routing]
                if not entry:
                    # routing info is missing, need to try again later.
                    retry.append(uuid)
                    continue
                if 'asn' in entry and entry['asn'] is None:
                    self.logger.warning(f"Unable to find the AS number associated to {data['ip']} - {data['datetime']} (got None). This should not happen...")
                    continue
                if 'prefix' in entry and entry['prefix'] is None:
                    self.logger.warning(f"Unable to find the prefix associated to {data['ip']} - {data['datetime']} (got None). This should not happen...")
                    continue

                # Format: <YYYY-MM-DD>|sources -> set([<source>, ...])
                ardb_pipeline.sadd(f"{data['date']}|sources", data['source'])

                # Format: <YYYY-MM-DD>|<source> -> set([<asn>, ...])
                ardb_pipeline.sadd(f"{data['date']}|{data['source']}", entry['asn'])
                # Format: <YYYY-MM-DD>|<source>|<asn> -> set([<prefix>, ...])
                ardb_pipeline.sadd(f"{data['date']}|{data['source']}|{entry['asn']}", entry['prefix'])

                # Format: <YYYY-MM-DD>|<source>|<asn>|<prefix> -> set([<ip>|<datetime>, ...])
                ardb_pipeline.sadd(f"{data['date']}|{data['source']}|{entry['asn']}|{entry['prefix']}",
                                   f"{data['ip']}|{data['datetime']}")
                done.append(uuid)
            ardb_pipeline.execute()
            p = self.redis_sanitized.pipeline(transaction=False)
            if done:
                p.delete(*done)
            if retry:
                p.sadd('to_insert', *retry)
            p.execute()
        unset_running(self.__class__.__name__)
