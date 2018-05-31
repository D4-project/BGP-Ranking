#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import TypeVar
import datetime
from datetime import timedelta
from dateutil.parser import parse

import logging
from redis import StrictRedis

from .libs.helpers import get_socket_path
from .libs.exceptions import InvalidDateFormat

Dates = TypeVar('Dates', datetime.datetime, datetime.date, str)


class Querying():

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

    def asns_global_ranking(self, date: Dates=datetime.date.today(), source: str='', ipversion: str='v4', limit: int=100):
        '''Aggregated ranking of all the ASNs known in the system, weighted by source.'''
        d = self.__normalize_date(date)
        if source:
            key = f'{d}|{source}|asns|{ipversion}'
        else:
            key = f'{d}|asns|{ipversion}'
        return self.ranking.zrevrange(key, start=0, end=limit, withscores=True)

    def asn_details(self, asn: int, date: Dates= datetime.date.today(), source: str='', ipversion: str='v4'):
        '''Aggregated ranking of all the prefixes anounced by the given ASN, weighted by source.'''
        d = self.__normalize_date(date)
        if source:
            key = f'{d}|{source}|{asn}|{ipversion}|prefixes'
        else:
            key = f'{d}|{asn}|{ipversion}'
        return self.ranking.zrevrange(key, start=0, end=-1, withscores=True)

    def asn_rank(self, asn: int, date: Dates=datetime.date.today(), source: str='', ipversion: str='v4'):
        '''Get the rank of a single ASN, weighted by source.'''
        d = self.__normalize_date(date)
        if source:
            key = f'{d}|{source}|{asn}|{ipversion}'
        else:
            key = f'{d}|asns|{ipversion}'
        return self.ranking.zscore(key, asn)

    def get_sources(self, date: Dates=datetime.date.today()):
        '''Get the sources availables for a specific day (default: today).'''
        d = self.__normalize_date(date)
        key = f'{d}|sources'
        return self.storage.smembers(key)

    def get_asn_descriptions(self, asn: int, all_descriptions=False):
        descriptions = self.asn_meta.hgetall(f'{asn}|descriptions')
        if all_descriptions or not descriptions:
            return descriptions
        return descriptions[sorted(descriptions.keys(), reverse=True)[0]]

    def get_asn_history(self, asn: int, period: int=100, source: str='', ipversion: str='v4'):
        to_return = []
        today = datetime.date.today()
        for i in range(period):
            date = today - timedelta(days=i)
            rank = self.asn_rank(asn, date, source, ipversion)
            if rank is None:
                rank = 0
            to_return.insert(0, (date.isoformat(), rank))
        return to_return
