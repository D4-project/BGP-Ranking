#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import re

from redis import ConnectionPool, Redis
from redis.connection import UnixDomainSocketConnection

from .default import get_config, get_socket_path

from typing import TypeVar, Union, Optional, Dict, Any, List, Tuple
import datetime
from datetime import timedelta
from dateutil.parser import parse
from collections import defaultdict

import json

from .default import InvalidDateFormat
from .helpers import get_modules
from .statsripe import StatsRIPE

Dates = TypeVar('Dates', datetime.datetime, datetime.date, str)


class BGPRanking():

    def __init__(self) -> None:
        self.logger = logging.getLogger(f'{self.__class__.__name__}')
        self.logger.setLevel(get_config('generic', 'loglevel'))

        self.cache_pool: ConnectionPool = ConnectionPool(connection_class=UnixDomainSocketConnection,
                                                         path=get_socket_path('cache'), decode_responses=True)

        self.storage = Redis(get_config('generic', 'storage_db_hostname'), get_config('generic', 'storage_db_port'), decode_responses=True)
        self.asn_meta = Redis(get_config('generic', 'storage_db_hostname'), get_config('generic', 'storage_db_port'), decode_responses=True)
        self.ranking = Redis(get_config('generic', 'ranking_db_hostname'), get_config('generic', 'ranking_db_port'))

    @property
    def cache(self):
        return Redis(connection_pool=self.cache_pool, db=1)

    def check_redis_up(self) -> bool:
        return self.cache.ping()

    def __normalize_date(self, date: Optional[Dates]) -> str:
        if not date:
            return datetime.date.today().isoformat()
        if isinstance(date, datetime.datetime):
            return date.date().isoformat()
        elif isinstance(date, datetime.date):
            return date.isoformat()
        elif isinstance(date, str):
            try:
                return parse(date).date().isoformat()
            except ValueError:
                raise InvalidDateFormat('Unable to parse the date. Should be YYYY-MM-DD.')

    def _ranking_cache_wrapper(self, key):
        if not self.cache.exists(key):
            if self.ranking.exists(key):
                try:
                    content: List[Tuple[bytes, float]] = self.ranking.zrangebyscore(key, '-Inf', '+Inf', withscores=True)
                    # Cache for 10 hours
                    self.cache.zadd(key, {value: rank for value, rank in content})
                    self.cache.expire(key, 36000)
                except Exception as e:
                    self.logger.exception(f'Something went poorly when caching {key}.')
                    raise e

    def asns_global_ranking(self, date: Optional[Dates]=None, source: Union[list, str]='',
                            ipversion: str='v4', limit: int=100):
        '''Aggregated ranking of all the ASNs known in the system, weighted by source.'''
        to_return: Dict[str, Any] = {
            'meta': {'ipversion': ipversion, 'limit': limit},
            'source': source,
            'response': set()
        }
        d = self.__normalize_date(date)
        to_return['meta']['date'] = d
        if source:
            if isinstance(source, list):
                keys = []
                for s in source:
                    key = f'{d}|{s}|asns|{ipversion}'
                    self._ranking_cache_wrapper(key)
                    keys.append(key)
                # union the ranked sets
                key = '|'.join(sorted(source)) + f'|{d}|asns|{ipversion}'
                if not self.cache.exists(key):
                    self.cache.zunionstore(key, keys)
            else:
                key = f'{d}|{source}|asns|{ipversion}'
        else:
            key = f'{d}|asns|{ipversion}'
        self._ranking_cache_wrapper(key)
        to_return['response'] = self.cache.zrevrange(key, start=0, end=limit, withscores=True)
        return to_return

    def asn_details(self, asn: int, date: Optional[Dates]=None, source: Union[list, str]='',
                    ipversion: str='v4'):
        '''Aggregated ranking of all the prefixes anounced by the given ASN, weighted by source.'''
        to_return: Dict[str, Any] = {
            'meta': {'asn': asn, 'ipversion': ipversion, 'source': source},
            'response': set()
        }

        d = self.__normalize_date(date)
        to_return['meta']['date'] = d
        if source:
            if isinstance(source, list):
                keys = []
                for s in source:
                    key = f'{d}|{s}|{asn}|{ipversion}|prefixes'
                    self._ranking_cache_wrapper(key)
                    keys.append(key)
                # union the ranked sets
                key = '|'.join(sorted(source)) + f'|{d}|{asn}|{ipversion}'
                if not self.cache.exists(key):
                    self.cache.zunionstore(key, keys)
            else:
                key = f'{d}|{source}|{asn}|{ipversion}|prefixes'
        else:
            key = f'{d}|{asn}|{ipversion}'
        self._ranking_cache_wrapper(key)
        to_return['response'] = self.cache.zrevrange(key, start=0, end=-1, withscores=True)
        return to_return

    def asn_rank(self, asn: int, date: Optional[Dates]=None, source: Union[list, str]='',
                 ipversion: str='v4', with_position: bool=False):
        '''Get the rank of a single ASN, weighted by source.'''
        to_return: Dict[str, Any] = {
            'meta': {'asn': asn, 'ipversion': ipversion,
                     'source': source, 'with_position': with_position},
            'response': 0.0
        }

        d = self.__normalize_date(date)
        to_return['meta']['date'] = d
        if source:
            to_return['meta']['source'] = source
            if isinstance(source, list):
                keys = []
                for s in source:
                    key = f'{d}|{s}|{asn}|{ipversion}'
                    self._ranking_cache_wrapper(key)
                    keys.append(key)
                r = sum(float(self.cache.get(key)) for key in keys if self.cache.exists(key))
            else:
                key = f'{d}|{source}|{asn}|{ipversion}'
                self._ranking_cache_wrapper(key)
                r = self.cache.get(key)
        else:
            key = f'{d}|asns|{ipversion}'
            self._ranking_cache_wrapper(key)
            r = self.cache.zscore(key, asn)
        if not r:
            r = 0
        if with_position and not source:
            position = self.cache.zrevrank(key, asn)
            if position is not None:
                position += 1
            to_return['response'] = {'rank': float(r), 'position': position,
                                     'total_known_asns': self.cache.zcard(key)}
        else:
            to_return['response'] = float(r)
        return to_return

    def get_sources(self, date: Optional[Dates]=None):
        '''Get the sources availables for a specific day (default: today).'''
        to_return: Dict[str, Any] = {'meta': {}, 'response': set()}

        d = self.__normalize_date(date)
        to_return['meta']['date'] = d
        key = f'{d}|sources'
        to_return['response'] = self.storage.smembers(key)
        return to_return

    def get_asn_descriptions(self, asn: int, all_descriptions=False) -> Dict[str, Any]:
        to_return: Dict[str, Union[Dict, List, str]] = {
            'meta': {'asn': asn, 'all_descriptions': all_descriptions},
            'response': []
        }
        descriptions = self.asn_meta.hgetall(f'{asn}|descriptions')
        if all_descriptions or not descriptions:
            to_return['response'] = descriptions
        else:
            to_return['response'] = descriptions[sorted(descriptions.keys(), reverse=True)[0]]
        return to_return

    def get_prefix_ips(self, asn: int, prefix: str, date: Optional[Dates]=None,
                       source: Union[list, str]='', ipversion: str='v4'):
        to_return: Dict[str, Any] = {
            'meta': {'asn': asn, 'prefix': prefix, 'ipversion': ipversion,
                     'source': source},
            'response': defaultdict(list)
        }

        d = self.__normalize_date(date)
        to_return['meta']['date'] = d

        if source:
            to_return['meta']['source'] = source
            if isinstance(source, list):
                sources = source
            else:
                sources = [source]
        else:
            sources = self.get_sources(d)['response']

        for source in sources:
            ips = set([ip_ts.split('|')[0]
                       for ip_ts in self.storage.smembers(f'{d}|{source}|{asn}|{prefix}')])
            [to_return['response'][ip].append(source) for ip in ips]
        return to_return

    def get_asn_history(self, asn: int, period: int=100, source: Union[list, str]='',
                        ipversion: str='v4', date: Optional[Dates]=None):
        to_return: Dict[str, Any] = {
            'meta': {'asn': asn, 'period': period, 'ipversion': ipversion, 'source': source},
            'response': []
        }

        if date is None:
            python_date: datetime.date = datetime.date.today()
        elif isinstance(date, str):
            python_date = parse(date).date()
        elif isinstance(date, datetime.datetime):
            python_date = date.date()
        else:
            python_date = date

        to_return['meta']['date'] = python_date.isoformat()

        for i in range(period):
            d = python_date - timedelta(days=i)
            rank = self.asn_rank(asn, d, source, ipversion)
            if 'response' not in rank:
                rank = 0
            to_return['response'].insert(0, (d.isoformat(), rank['response']))
        return to_return

    def country_rank(self, country: str, date: Optional[Dates]=None, source: Union[list, str]='',
                     ipversion: str='v4'):
        to_return: Dict[str, Any] = {
            'meta': {'country': country, 'ipversion': ipversion, 'source': source},
            'response': []
        }

        d = self.__normalize_date(date)
        to_return['meta']['date'] = d

        ripe = StatsRIPE()
        response = ripe.country_asns(country, query_time=d, details=1)
        if (not response.get('data') or not response['data'].get('countries') or not
                response['data']['countries'][0].get('routed')):
            logging.warning(f'Invalid response: {response}')
            return 0, [(0, 0)]
        routed_asns = re.findall(r"AsnSingle\(([\d]*)\)", response['data']['countries'][0]['routed'])
        ranks = [self.asn_rank(asn, d, source, ipversion)['response'] for asn in routed_asns]
        to_return['response'] = [sum(ranks), zip(routed_asns, ranks)]
        return to_return

    def country_history(self, country: Union[list, str], period: int=30, source: Union[list, str]='',
                        ipversion: str='v4', date: Optional[Dates]=None):
        to_return: Dict[str, Any] = {
            'meta': {'country': country, 'ipversion': ipversion, 'source': source},
            'response': defaultdict(list)
        }
        if date is None:
            python_date: datetime.date = datetime.date.today()
        elif isinstance(date, str):
            python_date = parse(date).date()
        elif isinstance(date, datetime.datetime):
            python_date = date.date()
        else:
            python_date = date

        if isinstance(country, str):
            country = [country]
        for c in country:
            for i in range(period):
                d = python_date - timedelta(days=i)
                rank, details = self.country_rank(c, d, source, ipversion)['response']
                if rank is None:
                    rank = 0
                to_return['response'][c].insert(0, (d.isoformat(), rank, list(details)))
        return to_return

    def get_source_config(self):
        pass

    def get_sources_configs(self):
        loaded = []
        for modulepath in get_modules():
            with open(modulepath) as f:
                loaded.append(json.load(f))
        return {'{}-{}'.format(config['vendor'], config['name']): config for config in loaded}
