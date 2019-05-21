#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import TypeVar, Union
import datetime
from datetime import timedelta
from dateutil.parser import parse
from collections import defaultdict

import logging
import json
from redis import StrictRedis

from .libs.helpers import get_socket_path, get_config_path
from .libs.exceptions import InvalidDateFormat
from .libs.statsripe import StatsRIPE

Dates = TypeVar('Dates', datetime.datetime, datetime.date, str)


class Querying():

    def __init__(self, loglevel: int=logging.DEBUG):
        self.__init_logger(loglevel)
        self.storage = StrictRedis(unix_socket_path=get_socket_path('storage'), decode_responses=True)
        self.ranking = StrictRedis(unix_socket_path=get_socket_path('storage'), db=1)
        self.asn_meta = StrictRedis(unix_socket_path=get_socket_path('storage'), db=2, decode_responses=True)
        self.cache = StrictRedis(unix_socket_path=get_socket_path('cache'), db=1, decode_responses=True)

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

    def _ranking_cache_wrapper(self, key):
        if not self.cache.exists(key):
            if self.ranking.exists(key):
                key_dump = self.ranking.dump(key)
                # Cache for 10 hours
                self.cache.restore(key, 36000, key_dump, True)

    def asns_global_ranking(self, date: Dates=datetime.date.today(), source: Union[list, str]='',
                            ipversion: str='v4', limit: int=100):
        '''Aggregated ranking of all the ASNs known in the system, weighted by source.'''
        to_return = {'meta': {'ipversion': ipversion, 'limit': limit}, 'source': source,
                     'response': set()}

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

    def asn_details(self, asn: int, date: Dates= datetime.date.today(), source: Union[list, str]='',
                    ipversion: str='v4'):
        '''Aggregated ranking of all the prefixes anounced by the given ASN, weighted by source.'''
        to_return = {'meta': {'asn': asn, 'ipversion': ipversion, 'source': source},
                     'response': set()}

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

    def asn_rank(self, asn: int, date: Dates=datetime.date.today(), source: Union[list, str]='',
                 ipversion: str='v4', with_position: bool=False):
        '''Get the rank of a single ASN, weighted by source.'''
        to_return = {'meta': {'asn': asn, 'ipversion': ipversion,
                              'source': source, 'with_position': with_position},
                     'response': 0.0}

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
            to_return['response'] = {'rank': float(r), 'position': self.cache.zrevrank(key, asn) + 1,
                                     'total_known_asns': self.cache.zcard(key)}
        else:
            to_return['response'] = float(r)
        return to_return

    def get_sources(self, date: Dates=datetime.date.today()):
        '''Get the sources availables for a specific day (default: today).'''
        to_return = {'meta': {}, 'response': set()}

        d = self.__normalize_date(date)
        to_return['meta']['date'] = d
        key = f'{d}|sources'
        to_return['response'] = self.storage.smembers(key)
        return to_return

    def get_asn_descriptions(self, asn: int, all_descriptions=False):
        to_return = {'meta': {'asn': asn, 'all_descriptions': all_descriptions},
                     'response': []}
        descriptions = self.asn_meta.hgetall(f'{asn}|descriptions')
        if all_descriptions or not descriptions:
            to_return['response'] = descriptions
        else:
            to_return['response'] = descriptions[sorted(descriptions.keys(), reverse=True)[0]]
        return to_return

    def get_prefix_ips(self, asn: int, prefix: str, date: Dates=datetime.date.today(),
                       source: Union[list, str]='', ipversion: str='v4'):
        to_return = {'meta': {'asn': asn, 'prefix': prefix, 'ipversion': ipversion,
                              'source': source},
                     'response': defaultdict(list)}

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
                        ipversion: str='v4', date: Dates=datetime.date.today()):
        to_return = {'meta': {'asn': asn, 'period': period, 'ipversion': ipversion,
                              'source': source},
                     'response': []}

        if isinstance(date, str):
            date = parse(date).date()
        if date + timedelta(days=period / 3) > datetime.date.today():
            # the period to display will be around the date passed at least 2/3 before the date, at most 1/3 after
            # FIXME: That is not doing what it is supposed to...
            date = datetime.date.today()

        to_return['meta']['date'] = date.isoformat()

        for i in range(period):
            d = date - timedelta(days=i)
            rank = self.asn_rank(asn, d, source, ipversion)
            if 'response' not in rank:
                rank = 0
            to_return['response'].insert(0, (d.isoformat(), rank['response']))
        return to_return

    def country_rank(self, country: str, date: Dates=datetime.date.today(), source: Union[list, str]='',
                     ipversion: str='v4'):
        to_return = {'meta': {'country': country, 'ipversion': ipversion,
                              'source': source},
                     'response': []}

        d = self.__normalize_date(date)
        to_return['meta']['date'] = d

        ripe = StatsRIPE()
        response = ripe.country_asns(country, query_time=d, details=1)
        if (not response.get('data') or not response['data'].get('countries') or not
                response['data']['countries'][0].get('routed')):
            logging.warning(f'Invalid response: {response}')
            # FIXME: return something
            return 0, [(0, 0)]
        routed_asns = response['data']['countries'][0]['routed']
        ranks = [self.asn_rank(asn, d, source, ipversion)['response'] for asn in routed_asns]
        to_return['response'] = [sum(ranks), zip(routed_asns, ranks)]
        return to_return

    def country_history(self, country: Union[list, str], period: int=30, source: Union[list, str]='',
                        ipversion: str='v4', date: Dates=datetime.date.today()):
        to_return = {}
        to_return = {'meta': {'country': country, 'ipversion': ipversion,
                              'source': source},
                     'response': defaultdict(list)}

        if isinstance(date, str):
            date = parse(date).date()
        if date + timedelta(days=period / 3) > datetime.date.today():
            # the period to display will be around the date passed at least 2/3 before the date, at most 1/3 after
            date = datetime.date.today()

        if isinstance(country, str):
            country = [country]
        for c in country:
            for i in range(period):
                d = date - timedelta(days=i)
                rank, details = self.country_rank(c, d, source, ipversion)['response']
                if rank is None:
                    rank = 0
                to_return['response'][c].insert(0, (d.isoformat(), rank, list(details)))
        return to_return

    def get_source_config(self):
        pass

    def get_sources_configs(self):
        config_dir = get_config_path() / 'modules'
        loaded = []
        for modulepath in config_dir.glob('*.json'):
            with open(modulepath) as f:
                loaded.append(json.load(f))
        return {'{}-{}'.format(config['vendor'], config['name']): config for config in loaded}
