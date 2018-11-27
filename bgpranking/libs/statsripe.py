#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
from enum import Enum
from datetime import datetime, timedelta
from ipaddress import IPv4Address, IPv6Address, IPv4Network, IPv6Network
from typing import TypeVar
from .helpers import get_homedir, safe_create_dir
try:
    import simplejson as json
except ImportError:
    import json
from dateutil.parser import parse
import copy

IPTypes = TypeVar('IPTypes', IPv4Address, IPv6Address, 'str')
PrefixTypes = TypeVar('PrefixTypes', IPv4Network, IPv6Network, 'str')
TimeTypes = TypeVar('TimeTypes', datetime, 'str')


class ASNsTypes(Enum):
    transiting = 't'
    originating = 'o'
    all_types = 't,o'
    undefined = ''


class AddressFamilies(Enum):
    ipv4 = 'v4'
    ipv6 = 'v6'
    all_families = 'v4,v6'
    undefined = ''


class Noise(Enum):
    keep = 'keep'
    remove = 'filter'


class StatsRIPE():

    def __init__(self, sourceapp='bgpranking-ng - CIRCL'):
        self.url = "https://stat.ripe.net/data/{method}/data.json?{parameters}"
        self.sourceapp = sourceapp
        self.cache_dir = get_homedir() / 'rawdata' / 'stats_ripe'

    def __time_to_text(self, query_time: TimeTypes) -> str:
        if isinstance(query_time, datetime):
            return query_time.isoformat()
        return query_time

    def _get_cache(self, method, parameters):
        '''The dataset is updated every 8 hours (midnight, 8, 16).
            If parameters has a key 'query_time' on any of these hours, try to get it.
            If not, try to get the closest one.
            If it has nothing, assume non and try to get the closest timestamp
            When caching, get query_time from response['data']['query_time']
        '''
        parameters = copy.copy(parameters)
        if not parameters.get('query_time'):
            # use timedelta because the generation of the new dataset takes a while.
            parameters['query_time'] = (datetime.now() - timedelta(hours=8)).isoformat()

        d = parse(parameters['query_time'])
        if d.hour == 8 and d.minute == 0 and d.second == 0:
            pass
        else:
            d = d.replace(hour=min([0, 8, 16], key=lambda x: abs(x - d.hour)),
                          minute=0, second=0, microsecond=0)
            parameters['query_time'] = d.isoformat()
        cache_filename = '&'.join(['{}={}'.format(k, str(v).lower()) for k, v in parameters.items()])
        c_path = self.cache_dir / method / cache_filename
        if c_path.exists():
            with open(c_path, 'r') as f:
                return json.load(f)
        return False

    def _save_cache(self, method, parameters, response):
        parameters['query_time'] = response['data']['query_time']
        cache_filename = '&'.join(['{}={}'.format(k, str(v).lower()) for k, v in parameters.items()])
        safe_create_dir(self.cache_dir / method)
        c_path = self.cache_dir / method / cache_filename
        with open(c_path, 'w') as f:
            json.dump(response, f, indent=2)

    def _get(self, method: str, parameters: dict) -> dict:
        parameters['sourceapp'] = self.sourceapp
        cached = self._get_cache(method, parameters)
        if cached:
            return cached
        url = self.url.format(method=method, parameters='&'.join(['{}={}'.format(k, str(v).lower()) for k, v in parameters.items()]))
        response = requests.get(url)
        j_content = response.json()
        self._save_cache(method, parameters, j_content)
        return j_content

    def network_info(self, ip: IPTypes) -> dict:
        parameters = {'resource': ip}
        return self._get('network-info', parameters)

    def prefix_overview(self, prefix: PrefixTypes, min_peers_seeing: int= 0,
                        max_related: int=0, query_time: TimeTypes=None) -> dict:
        parameters = {'resource': prefix}
        if min_peers_seeing:
            parameters['min_peers_seeing'] = min_peers_seeing
        if max_related:
            parameters['max_related'] = max_related
        if query_time:
            parameters['query_time'] = self.__time_to_text(query_time)
        return self._get('prefix-overview', parameters)

    def ris_asns(self, query_time: TimeTypes=None, list_asns: bool=False, asn_types: ASNsTypes=ASNsTypes.undefined):
        parameters = {}
        if list_asns:
            parameters['list_asns'] = list_asns
        if asn_types:
            parameters['asn_types'] = asn_types.value
        if query_time:
            parameters['query_time'] = self.__time_to_text(query_time)
        return self._get('ris-asns', parameters)

    def ris_prefixes(self, asn: int, query_time: TimeTypes=None,
                     list_prefixes: bool=False, types: ASNsTypes=ASNsTypes.undefined,
                     af: AddressFamilies=AddressFamilies.undefined, noise: Noise=Noise.keep):
        parameters = {'resource': str(asn)}
        if query_time:
            parameters['query_time'] = self.__time_to_text(query_time)
        if list_prefixes:
            parameters['list_prefixes'] = list_prefixes
        if types:
            parameters['types'] = types.value
        if af:
            parameters['af'] = af.value
        if noise:
            parameters['noise'] = noise.value
        return self._get('ris-prefixes', parameters)

    def country_asns(self, country: str, details: int=0, query_time: TimeTypes=None):
        parameters = {'resource': country}
        if details:
            parameters['lod'] = details
        if query_time:
            parameters['query_time'] = self.__time_to_text(query_time)
        return self._get('country-asns', parameters)
