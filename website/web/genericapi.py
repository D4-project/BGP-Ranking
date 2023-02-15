#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Dict, Any, Union
from urllib.parse import urljoin

import requests

from flask import request, session
from flask_restx import Namespace, Resource, fields  # type: ignore

from bgpranking.default import get_config
from bgpranking.bgpranking import BGPRanking

from .helpers import load_session

api = Namespace('BGP Ranking API', description='API to query BGP Ranking.', path='/')

bgpranking: BGPRanking = BGPRanking()


@api.route('/redis_up')
@api.doc(description='Check if redis is up and running')
class RedisUp(Resource):

    def get(self):
        return bgpranking.check_redis_up()


@api.route('/ipasn_history/')
@api.route('/ipasn_history/<path:path>')
class IPASNProxy(Resource):

    def _proxy_url(self):
        if request.full_path[-1] == '?':
            full_path = request.full_path[:-1]
        else:
            full_path = request.full_path
        path_for_ipasnhistory = full_path.replace('/ipasn_history/', '')
        if path_for_ipasnhistory.startswith('?'):
            path_for_ipasnhistory = path_for_ipasnhistory.replace('?', 'ip?')
        if not path_for_ipasnhistory:
            path_for_ipasnhistory = 'ip'
        return urljoin(get_config('generic', 'ipasnhistory_url'), path_for_ipasnhistory)

    def get(self, path=''):
        url = self._proxy_url()
        return requests.get(url).json()

    def post(self, path=''):
        url = self._proxy_url()
        return requests.post(url, data=request.data).json()


# TODO: Add other parameters for asn_rank
asn_query_fields = api.model('ASNQueryFields', {
    'asn': fields.String(description='The Autonomus System Number to search', required=True)
})


@api.route('/json/asn')
class ASNRank(Resource):

    @api.doc(body=asn_query_fields)
    def post(self):
        # TODO
        # * Filter on date => if only returning one descr, return the desription at that date
        query: Dict[str, Any] = request.get_json(force=True)
        to_return: Dict[str, Union[str, Dict[str, Any]]] = {'meta': query, 'response': {}}
        if 'asn' not in query:
            to_return['error'] = f'You need to pass an asn - {query}'
            return to_return

        asn_description_query = {'asn': query['asn']}
        responses = bgpranking.get_asn_descriptions(**asn_description_query)['response']
        to_return['response']['asn_description'] = responses  # type: ignore

        asn_rank_query = {'asn': query['asn']}
        if 'date' in query:
            asn_rank_query['date'] = query['date']
        if 'source' in query:
            asn_rank_query['source'] = query['source']
        else:
            asn_rank_query['with_position'] = True
        if 'ipversion' in query:
            asn_rank_query['ipversion'] = query['ipversion']

        to_return['response']['ranking'] = bgpranking.asn_rank(**asn_rank_query)['response']  # type: ignore
        return to_return


asn_descr_fields = api.model('ASNDescriptionsFields', {
    'asn': fields.String(description='The Autonomus System Number to search', required=True),
    'all_descriptions': fields.Boolean(description='If true, returns all the descriptions instead of only the last one', default=False)
})


@api.route('/json/asn_descriptions')
class ASNDescription(Resource):

    @api.doc(body=asn_descr_fields)
    def post(self):
        query: Dict = request.get_json(force=True)
        to_return: Dict[str, Union[str, Dict[str, Any]]] = {'meta': query, 'response': {}}
        if 'asn' not in query:
            to_return['error'] = f'You need to pass an asn - {query}'
            return to_return

        to_return['response']['asn_descriptions'] = bgpranking.get_asn_descriptions(**query)['response']  # type: ignore
        return to_return


# TODO: Add other parameters for get_asn_history
asn_history_fields = api.model('ASNQueryFields', {
    'asn': fields.String(description='The Autonomus System Number to search', required=True)
})


@api.route('/json/asn_history')
class ASNHistory(Resource):

    def get(self):
        load_session()
        if 'asn' in session:
            return bgpranking.get_asn_history(**session)

    @api.doc(body=asn_history_fields)
    def post(self):
        query: Dict = request.get_json(force=True)
        to_return: Dict[str, Union[str, Dict[str, Any]]] = {'meta': query, 'response': {}}
        if 'asn' not in query:
            to_return['error'] = f'You need to pass an asn - {query}'
            return to_return

        to_return['response']['asn_history'] = bgpranking.get_asn_history(**query)['response']  # type: ignore
        return to_return


# TODO: Add other parameters for country_history
coutry_history_fields = api.model('CountryHistoryFields', {
    'country': fields.String(description='The Country Code', required=True)
})


@api.route('/json/country_history')
class CountryHistory(Resource):

    def get(self):
        load_session()
        return bgpranking.country_history(**session)

    @api.doc(body=coutry_history_fields)
    def post(self):
        query: Dict = request.get_json(force=True)
        to_return: Dict[str, Union[str, Dict[str, Any]]] = {'meta': query, 'response': {}}
        to_return['response']['country_history'] = bgpranking.country_history(**query)['response']  # type: ignore
        return to_return


# TODO: Add other parameters for asns_global_ranking
asns_global_ranking_fields = api.model('ASNsGlobalRankingFields', {
    'date': fields.String(description='The date')
})


@api.route('/json/asns_global_ranking')
class ASNsGlobalRanking(Resource):

    @api.doc(body=asns_global_ranking_fields)
    def post(self):
        query: Dict = request.get_json(force=True)
        to_return: Dict[str, Union[str, Dict[str, Any]]] = {'meta': query, 'response': {}}
        to_return['response'] = bgpranking.asns_global_ranking(**query)['response']
        return to_return
