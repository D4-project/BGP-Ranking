#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from redis import Redis
from ipaddress import ip_network
import requests
import gzip
from io import BytesIO
from collections import defaultdict
import re
import time
from .libs.helpers import set_running, unset_running


# Dataset source: Routeviews Prefix to AS mappings Dataset for IPv4 and IPv6
# http://www.caida.org/data/routing/routeviews-prefix2as.xml


class PrefixDatabase():

    def __init__(self, loglevel: int=logging.DEBUG):
        self.__init_logger(loglevel)
        self.prefix_cache = Redis(host='localhost', port=6582, db=0, decode_responses=True)
        self.ipv6_url = 'http://data.caida.org/datasets/routing/routeviews6-prefix2as/{}'
        self.ipv4_url = 'http://data.caida.org/datasets/routing/routeviews-prefix2as/{}'

    def __init_logger(self, loglevel):
        self.logger = logging.getLogger('{}'.format(self.__class__.__name__))
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
        if path == self.prefix_cache.get('current|{}'.format(address_family)):
            self.logger.debug('Same file already loaded: {}'.format(path))
            return False, path
        return True, path

    def _init_routes(self, address_family, root_url, path):
        self.logger.debug('Loading {}'.format(path))
        r = requests.get(root_url.format(path))
        to_import = defaultdict(lambda: {address_family: set(), 'ipcount': 0})
        with gzip.open(BytesIO(r.content), 'r') as f:
            for line in f:
                prefix, length, asns = line.decode().strip().split('\t')
                # The meaning of AS set and multi-origin AS in unclear. Taking the first ASN in the list only.
                asn = re.split('[,_]', asns)[0]
                network = ip_network('{}/{}'.format(prefix, length))
                to_import[asn][address_family].add(str(network))
                to_import[asn]['ipcount'] += network.num_addresses

        p = self.prefix_cache.pipeline()
        p.sadd('asns', *to_import.keys())
        for asn, data in to_import.items():
            p.sadd('{}|{}'.format(asn, address_family), *data[address_family])
            p.set('{}|{}|ipcount'.format(asn, address_family), data['ipcount'])
        p.set('current|{}'.format(address_family), path)
        p.execute()
        return True

    def load_prefixes(self):
        set_running(self.__class__.__name__)
        self.prefix_cache.delete('ready')
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
