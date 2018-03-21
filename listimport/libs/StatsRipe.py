#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
from enum import Enum
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address, IPv4Network, IPv6Network
from typing import TypeVar

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

    def __time_to_text(self, query_time: TimeTypes) -> str:
        if type(query_time, datetime):
            return query_time.isoformat()
        return query_time

    def _get(self, method: str, parameters: dict) -> dict:
        parameters['sourceapp'] = self.sourceapp
        url = self.url.format(method=method, parameters='&'.join(['{}={}'.format(k, str(v).lower()) for k, v in parameters.items()]))
        response = requests.get(url)
        return response.json()

    async def network_info(self, ip: IPTypes) -> dict:
        parameters = {'resource': ip}
        return self._get('network-info', parameters)

    async def prefix_overview(self, prefix: PrefixTypes, min_peers_seeing: int= 0,
                              max_related: int=0, query_time: TimeTypes=None) -> dict:
        parameters = {'resource': prefix}
        if min_peers_seeing:
            parameters['min_peers_seeing'] = min_peers_seeing
        if max_related:
            parameters['max_related'] = max_related
        if query_time:
            parameters['query_time'] = self.__time_to_text(query_time)
        return self._get('prefix-overview', parameters)

    async def ris_asns(self, query_time: TimeTypes=None, list_asns: bool=False, asn_types: ASNsTypes=ASNsTypes.undefined):
        parameters = {}
        if list_asns:
            parameters['list_asns'] = list_asns
        if asn_types:
            parameters['asn_types'] = asn_types.value
        if query_time:
            if type(query_time, datetime):
                parameters['query_time'] = query_time.isoformat()
            else:
                parameters['query_time'] = query_time
        return self._get('ris-asns', parameters)

    async def ris_prefixes(self, asn: int, query_time: TimeTypes=None,
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
