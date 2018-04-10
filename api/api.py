#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import TypeVar
import datetime
from enum import Enum
from dateutil.parser import parse

import logging
from redis import StrictRedis

from bgpranking.libs.helpers import get_socket_path
from bgpranking.libs.exceptions import InvalidDateFormat

Dates = TypeVar('Dates', datetime.datetime, datetime.date, str)


class IPVersion(Enum):
    v4 = 'v4'
    v6 = 'v6'


class BGPRanking():

    def __init__(self, loglevel: int=logging.DEBUG):
        self.__init_logger(loglevel)
        self.storage = StrictRedis(unix_socket_path=get_socket_path('storage'), decode_responses=True)
        self.ranking = StrictRedis(unix_socket_path=get_socket_path('storage'), db=1, decode_responses=True)
        self.asn_meta = StrictRedis(unix_socket_path=get_socket_path('storage'), db=2, decode_responses=True)

    def __init_logger(self, loglevel: int):
        self.logger = logging.getLogger(f'{self.__class__.__name__}')
        self.logger.setLevel(loglevel)

    def __normalize_date(self, date: Dates):
        if isinstance(date, datetime.datetime):
            return date.date().isoformat()
        elif isinstance(date, datetime.date):
            return date.isoformat()
        elif isinstance(date, str):
            try:
                return parse(date).date().isoformat()
            except ValueError:
                raise InvalidDateFormat('Unable to parse the date. Should be YYYY-MM-DD.')

    def asns_global_ranking(self, date: Dates=datetime.date.today(),
                            ipversion: IPVersion=IPVersion.v4, limit: int=100):
        '''Aggregated ranking of all the ASNs known in the system, weighted by source.'''
        d = self.__normalize_date(date)
        key = f'{d}|asns|{ipversion.value}'
        return self.ranking.zrevrange(key, start=0, end=limit, withscores=True)

    def asn_details(self, asn: int, date: Dates= datetime.date.today(), ipversion: IPVersion=IPVersion.v4):
        '''Aggregated ranking of all the prefixes anounced by the given ASN, weighted by source.'''
        d = self.__normalize_date(date)
        key = f'{d}|{asn}|{ipversion.value}'
        return self.ranking.zrevrange(key, start=0, end=-1, withscores=True)

    def asn_rank(self, asn: int, date: Dates= datetime.date.today(), ipversion: IPVersion=IPVersion.v4):
        '''Get the rank of a single ASN, weighted by source.'''
        d = self.__normalize_date(date)
        key = f'{d}|asns|{ipversion.value}'
        return self.ranking.zscore(key, asn)

    def asn_rank_by_source(self, asn: int, source: str, date: Dates= datetime.date.today(), ipversion: IPVersion=IPVersion.v4):
        '''Get the rank of a single ASN, not weighted by source.'''
        d = self.__normalize_date(date)
        key = f'{d}|{source}|{asn}|rank{ipversion.value}'
        return self.ranking.get(key)

    def asn_details_by_source(self, source: str, asn: int, date: Dates= datetime.date.today(),
                              ipversion: IPVersion=IPVersion.v4):
        '''Get the rank of all the prefixes announced by an ASN, not weighted by source.'''
        d = self.__normalize_date(date)
        key = f'{d}|{source}|{asn}|rank{ipversion.value}|prefixes'
        return self.ranking.zrevrange(key, start=0, end=-1, withscores=True)
