#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import time

from typing import List

from redis import Redis

from bgpranking.default import get_socket_path, AbstractManager, get_config
from bgpranking.helpers import get_ipasn, sanity_check_ipasn


logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO)


class DBInsertManager(AbstractManager):

    def __init__(self, loglevel: int=logging.INFO):
        super().__init__(loglevel)
        self.script_name = 'db_insert'
        self.kvrocks_storage = Redis(get_config('generic', 'storage_db_hostname'), get_config('generic', 'storage_db_port'), decode_responses=True)
        self.redis_sanitized = Redis(unix_socket_path=get_socket_path('prepare'), db=0, decode_responses=True)
        self.ipasn = get_ipasn()
        self.logger.debug('Starting import')

    def _to_run_forever(self):
        ready, message = sanity_check_ipasn(self.ipasn)
        if not ready:
            # Try again later.
            self.logger.warning(message)
            return
        self.logger.debug(message)

        while True:
            if self.shutdown_requested():
                break
            try:
                if not self.ipasn.is_up:
                    break
            except Exception:
                self.logger.warning('Unable to query ipasnhistory')
                time.sleep(10)
                continue
            uuids: List[str] = self.redis_sanitized.spop('to_insert', 100)  # type: ignore
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
                for_query.append({'ip': data['ip'], 'address_family': data['address_family'],
                                  'date': data['datetime'], 'precision_delta': {'days': 3}})
            try:
                responses = self.ipasn.mass_query(for_query)
            except Exception:
                self.logger.exception('Mass query in IPASN History failed, trying again later.')
                # Rollback the spop
                self.redis_sanitized.sadd('to_insert', *uuids)
                time.sleep(10)
                continue
            retry = []
            done = []
            ardb_pipeline = self.kvrocks_storage.pipeline(transaction=False)
            for i, uuid in enumerate(uuids):
                data = sanitized_data[i]
                if not data:
                    self.logger.warning(f'No data for UUID {uuid}. This should not happen, but lets move on.')
                    done.append(uuid)
                    continue
                routing_info = responses['responses'][i]['response']  # our queries are on one single date, not a range
                # Data gathered from IPASN History:
                # * IP Block of the IP
                # * AS number
                if 'error' in routing_info:
                    self.logger.warning(f"Unable to find routing information for {data['ip']} - {data['datetime']}: {routing_info['error']}")
                    done.append(uuid)
                    continue
                # Single date query, getting from the object
                datetime_routing = list(routing_info.keys())[0]
                entry = routing_info[datetime_routing]
                if not entry:
                    # routing info is missing, need to try again later.
                    retry.append(uuid)
                    continue
                if 'asn' in entry and entry['asn'] in [None, '0']:
                    self.logger.warning(f"Unable to find the AS number associated to {data['ip']} - {data['datetime']} (got {entry['asn']}).")
                    done.append(uuid)
                    continue
                if 'prefix' in entry and entry['prefix'] in [None, '0.0.0.0/0', '::/0']:
                    self.logger.warning(f"Unable to find the prefix associated to {data['ip']} - {data['datetime']} (got {entry['prefix']}).")
                    done.append(uuid)
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


def main():
    dbinsert = DBInsertManager()
    dbinsert.run(sleep_in_sec=120)


if __name__ == '__main__':
    main()
