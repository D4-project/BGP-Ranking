#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from redis import StrictRedis
from ipaddress import ip_network
import requests
import gzip
from io import BytesIO
from collections import defaultdict
import re
import time
from .libs.helpers import set_running, unset_running, get_socket_path
from dateutil.parser import parse

# Dataset source: Routeviews Prefix to AS mappings Dataset for IPv4 and IPv6
# http://www.caida.org/data/routing/routeviews-prefix2as.xml


class PrefixDatabase():

    def __init__(self, loglevel: int=logging.DEBUG):
        self.__init_logger(loglevel)
        self.prefix_cache = StrictRedis(unix_socket_path=get_socket_path('prefixes'), db=0, decode_responses=True)
        self.asn_meta = StrictRedis(unix_socket_path=get_socket_path('storage'), db=2, decode_responses=True)
        self.ipv6_url = 'http://data.caida.org/datasets/routing/routeviews6-prefix2as/{}'
        self.ipv4_url = 'http://data.caida.org/datasets/routing/routeviews-prefix2as/{}'

    def __init_logger(self, loglevel):
        self.logger = logging.getLogger(f'{self.__class__.__name__}')
        self.logger.setLevel(loglevel)

    def update_required(self):
        v4_is_new, v4_path = self._has_new('v4', self.ipv4_url)
        v6_is_new, v6_path = self._has_new('v6', self.ipv6_url)
        if any([v4_is_new, v6_is_new]):
            self.logger.info('Prefix update required.')
        else:
            self.logger.debug('No prefix update required.')
        return any([v4_is_new, v6_is_new])

    def _has_new(self, address_family, root_url):
        r = requests.get(root_url.format('pfx2as-creation.log'))
        last_entry = r.text.split('\n')[-2]
        path = last_entry.split('\t')[-1]
        if path == self.prefix_cache.get(f'current|{address_family}'):
            self.logger.debug(f'Same file already loaded: {path}')
            return False, path
        return True, path

    def _init_routes(self, address_family, root_url, path) -> bool:
        self.logger.debug(f'Loading {path}')
        date = parse(re.findall('(?:.*)/(?:.*)/routeviews-rv[2,6]-(.*)-(?:.*).pfx2as.gz', path)[0]).date().isoformat()
        r = requests.get(root_url.format(path))
        to_import = defaultdict(lambda: {address_family: set(), 'ipcount': 0})
        with gzip.open(BytesIO(r.content), 'r') as f:
            for line in f:
                prefix, length, asns = line.decode().strip().split('\t')
                # The meaning of AS set and multi-origin AS in unclear. Taking the first ASN in the list only.
                asn = re.split('[,_]', asns)[0]
                network = ip_network(f'{prefix}/{length}')
                to_import[asn][address_family].add(str(network))
                to_import[asn]['ipcount'] += network.num_addresses

        p = self.prefix_cache.pipeline()
        p_asn_meta = self.asn_meta.pipeline()
        p.sadd('asns', *to_import.keys())
        p_asn_meta.set(f'{address_family}|last', date)  # Not necessarely today
        p_asn_meta.sadd(f'{date}|asns|{address_family}', *to_import.keys())
        for asn, data in to_import.items():
            p.sadd(f'{asn}|{address_family}', *data[address_family])
            p.set(f'{asn}|{address_family}|ipcount', data['ipcount'])
            p_asn_meta.sadd(f'{date}|{asn}|{address_family}', *data[address_family])
            p_asn_meta.set(f'{date}|{asn}|{address_family}|ipcount', data['ipcount'])
        p.set(f'current|{address_family}', path)
        p.execute()
        p_asn_meta.execute()
        return True

    def load_prefixes(self):
        set_running(self.__class__.__name__)
        self.prefix_cache.delete('ready')
        self.asn_meta.delete('v4|last')
        self.asn_meta.delete('v6|last')
        self.logger.info('Prefix update starting in a few seconds.')
        time.sleep(15)
        v4_is_new, v4_path = self._has_new('v4', self.ipv4_url)
        v6_is_new, v6_path = self._has_new('v6', self.ipv6_url)

        self.prefix_cache.flushdb()
        # TODO: Add a catchall for everything that isn't announced so we can track that down later on
        self._init_routes('v6', self.ipv6_url, v6_path)
        self._init_routes('v4', self.ipv4_url, v4_path)
        self.prefix_cache.set('ready', 1)
        self.logger.info('Prefix update complete.')
        unset_running(self.__class__.__name__)
