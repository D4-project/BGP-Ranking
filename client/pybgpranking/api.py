#!/usr/bin/env python3
# -*- coding: utf-8 -*-

try:
    import simplejson as json
except ImportError:
    import json

from typing import Union

import requests
from urllib.parse import urljoin
from datetime import date


class BGPRanking():

    def __init__(self, root_url: str='https://bgpranking-ng.circl.lu/'):
        self.root_url = root_url
        if not self.root_url.endswith('/'):
            self.root_url += '/'
        self.session = requests.session()

    @property
    def is_up(self):
        r = self.session.head(self.root_url)
        return r.status_code == 200

    def query(self, asn: str, address_family: str='v4', date: str=None,
              source: Union[list, str]=''):
        '''Launch a query.
        :param asn: ASN to lookup
        :param address_family: v4 or v6
        :param date: Exact date to lookup. Fallback to most recent available.
        :param source: Source to query. Can be a list of sources.
        '''
        to_query = {'asn': asn, 'address_family': address_family}
        if date:
            to_query['date'] = date
        if source:
            to_query['source'] = source
        r = self.session.post(urljoin(self.root_url, '/json/asn'), data=json.dumps(to_query))
        return r.json()

    def asns_global_ranking(self, date: str=date.today().isoformat(), address_family: str='v4', limit: int=100):
        '''Get the top `limit` ASNs, from worse to best'''
        to_query = {'date': date, 'ipversion': address_family, 'limit': limit}
        r = self.session.post(urljoin(self.root_url, '/json/asns_global_ranking'), data=json.dumps(to_query))
        return r.json()
