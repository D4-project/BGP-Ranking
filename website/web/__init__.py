#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import pkg_resources

from collections import defaultdict
from datetime import date, timedelta
from urllib.parse import urljoin
from typing import Dict, Any, Tuple, List, Optional, Union

import pycountry  # type: ignore
import requests

from flask import Flask, render_template, request, session, Response, redirect, url_for
from flask_bootstrap import Bootstrap  # type: ignore
from flask_restx import Api  # type: ignore

from bgpranking.bgpranking import BGPRanking
from bgpranking.default import get_config
from bgpranking.helpers import get_ipasn

from .genericapi import api as generic_api
from .helpers import get_secret_key
from .proxied import ReverseProxied

app = Flask(__name__)

app.wsgi_app = ReverseProxied(app.wsgi_app)  # type: ignore

app.config['SECRET_KEY'] = get_secret_key()

Bootstrap(app)
app.config['BOOTSTRAP_SERVE_LOCAL'] = True

bgpranking = BGPRanking()


# ############# Helpers #############

def load_session():
    if request.method == 'POST':
        d = request.form
    elif request.method == 'GET':
        d = request.args  # type: ignore

    for key in d:
        if '_all' in d.getlist(key):
            session.pop(key, None)
        else:
            values = [v for v in d.getlist(key) if v]
            if values:
                if len(values) == 1:
                    session[key] = values[0]
                else:
                    session[key] = values

    # Edge cases
    if 'asn' in session:
        session.pop('country', None)
    elif 'country' in session:
        session.pop('asn', None)
    if 'date' not in session:
        session['date'] = (date.today() - timedelta(days=1)).isoformat()


def get_country_codes():
    for c in pycountry.countries:
        yield c.alpha_2, c.name

# ############# Helpers ######################


# ############# Web UI #############

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'HEAD':
        # Just returns ack if the webserver is running
        return 'Ack'
    load_session()
    sources = bgpranking.get_sources(date=session['date'])['response']
    session.pop('asn', None)
    session.pop('country', None)
    ranks = bgpranking.asns_global_ranking(limit=100, **session)['response']
    r = [(asn, rank, bgpranking.get_asn_descriptions(int(asn))['response']) for asn, rank in ranks]
    return render_template('index.html', ranks=r, sources=sources, countries=get_country_codes(), **session)


@app.route('/asn', methods=['GET', 'POST'])
def asn_details():
    load_session()
    if 'asn' not in session:
        return redirect(url_for('/'))
    asn_descriptions = bgpranking.get_asn_descriptions(asn=session['asn'], all_descriptions=True)['response']
    sources = bgpranking.get_sources(date=session['date'])['response']
    prefix = session.pop('prefix', None)
    ranks = bgpranking.asn_details(**session)['response']
    if prefix:
        prefix_ips = bgpranking.get_prefix_ips(prefix=prefix, **session)['response']
        prefix_ips = [(ip, sorted(sources)) for ip, sources in prefix_ips.items()]
        prefix_ips.sort(key=lambda entry: len(entry[1]), reverse=True)
    else:
        prefix_ips = []
    return render_template('asn.html', sources=sources, ranks=ranks,
                           prefix_ips=prefix_ips, asn_descriptions=asn_descriptions, **session)


@app.route('/country', methods=['GET', 'POST'])
def country():
    load_session()
    sources = bgpranking.get_sources(date=session['date'])['response']
    return render_template('country.html', sources=sources, countries=get_country_codes(), **session)


@app.route('/country_history_callback', methods=['GET', 'POST'])
def country_history_callback():
    history_data: Dict[str, Tuple[str, str, List[Any]]]
    history_data = request.get_json(force=True)  # type: ignore
    to_display = []
    mapping: Dict[str, Any] = defaultdict(dict)
    dates = []
    all_asns = set([])
    for country, foo in history_data.items():
        for d, r_sum, details in foo:
            dates.append(d)
            for detail in details:
                asn, r = detail
                all_asns.add(asn)
                mapping[asn][d] = r

        to_display_temp = [[country] + dates]
        for a in sorted(list(all_asns), key=int):
            line = [a]
            for d in dates:
                if mapping[a].get(d) is not None:
                    line.append(round(mapping[a].get(d), 3))
                else:
                    line.append('N/A')
            to_display_temp.append(line)
        to_display.append(to_display_temp)
    return render_template('country_asn_map.html', to_display=to_display)


@app.route('/ipasn', methods=['GET', 'POST'])
def ipasn():
    d: Optional[Dict] = None
    if request.method == 'POST':
        d = request.form
    elif request.method == 'GET':
        d = request.args

    if not d or 'ip' not in d:
        return render_template('ipasn.html')
    else:
        if isinstance(d['ip'], list):
            ip = d['ip'][0]
        else:
            ip = d['ip']
    ipasn = get_ipasn()
    response = ipasn.query(first=(date.today() - timedelta(days=60)).isoformat(),
                           aggregate=True, ip=ip)
    for r in response['response']:
        r['asn_descriptions'] = []
        asn_descriptions = bgpranking.get_asn_descriptions(asn=r['asn'], all_descriptions=True)['response']
        for timestamp in sorted(asn_descriptions.keys()):
            if r['first_seen'] <= timestamp <= r['last_seen']:
                r['asn_descriptions'].append(asn_descriptions[timestamp])

        if not r['asn_descriptions'] and timestamp <= r['last_seen']:
            r['asn_descriptions'].append(asn_descriptions[timestamp])

    return render_template('ipasn.html', ipasn_details=response['response'],
                           **response['meta'])


# ############# Web UI #############


# ############# Json outputs #############

@app.route('/ipasn_history/', defaults={'path': ''}, methods=['GET', 'POST'])
@app.route('/ipasn_history/<path:path>', methods=['GET', 'POST'])
def ipasn_history_proxy(path):

    path_for_ipasnhistory = request.full_path.replace('/ipasn_history', '')
    if '/?' in path_for_ipasnhistory:
        path_for_ipasnhistory = path_for_ipasnhistory.replace('/?', '/ip?')
    proxied_url = urljoin(get_config('generic', 'ipasnhistory_url'), path_for_ipasnhistory)
    if request.method in ['GET', 'HEAD']:
        to_return = requests.get(proxied_url).json()
    elif request.method == 'POST':
        to_return = requests.post(proxied_url, data=request.data).json()
    return Response(json.dumps(to_return), mimetype='application/json')


@app.route('/json/asn', methods=['POST'])
def json_asn():
    # TODO
    # * Filter on date => if only returning one descr, return the desription at that date
    query: Dict[str, Any] = request.get_json(force=True)  # type: ignore
    to_return: Dict[str, Union[str, Dict[str, Any]]] = {'meta': query, 'response': {}}
    if 'asn' not in query:
        to_return['error'] = f'You need to pass an asn - {query}'
        return Response(json.dumps(to_return), mimetype='application/json')

    asn_description_query = {'asn': query['asn']}
    if 'all_descriptions' in query:
        asn_description_query['all_descriptions'] = query['all_descriptions']
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
    return Response(json.dumps(to_return), mimetype='application/json')


@app.route('/json/asn_descriptions', methods=['POST'])
def asn_description():
    query: Dict = request.get_json(force=True)  # type: ignore
    to_return: Dict[str, Union[str, Dict[str, Any]]] = {'meta': query, 'response': {}}
    if 'asn' not in query:
        to_return['error'] = f'You need to pass an asn - {query}'
        return Response(json.dumps(to_return), mimetype='application/json')

    to_return['response']['asn_descriptions'] = bgpranking.get_asn_descriptions(**query)['response']  # type: ignore
    return Response(json.dumps(to_return), mimetype='application/json')


@app.route('/json/asn_history', methods=['GET', 'POST'])
def asn_history():
    if request.method == 'GET':
        load_session()
        if 'asn' in session:
            return Response(json.dumps(bgpranking.get_asn_history(**session)), mimetype='application/json')

    query: Dict = request.get_json(force=True)  # type: ignore
    to_return: Dict[str, Union[str, Dict[str, Any]]] = {'meta': query, 'response': {}}
    if 'asn' not in query:
        to_return['error'] = f'You need to pass an asn - {query}'
        return Response(json.dumps(to_return), mimetype='application/json')

    to_return['response']['asn_history'] = bgpranking.get_asn_history(**query)['response']  # type: ignore
    return Response(json.dumps(to_return), mimetype='application/json')


@app.route('/json/country_history', methods=['GET', 'POST'])
def country_history():
    if request.method == 'GET':
        load_session()
        return Response(json.dumps(bgpranking.country_history(**session)), mimetype='application/json')

    query: Dict = request.get_json(force=True)  # type: ignore
    to_return: Dict[str, Union[str, Dict[str, Any]]] = {'meta': query, 'response': {}}
    to_return['response']['country_history'] = bgpranking.country_history(**query)['response']  # type: ignore
    return Response(json.dumps(to_return), mimetype='application/json')


@app.route('/json/asns_global_ranking', methods=['POST'])
def json_asns_global_ranking():
    query: Dict = request.get_json(force=True)  # type: ignore
    to_return: Dict[str, Union[str, Dict[str, Any]]] = {'meta': query, 'response': {}}
    to_return['response'] = bgpranking.asns_global_ranking(**query)['response']
    return Response(json.dumps(to_return), mimetype='application/json')

# ############# Json outputs #############


# Query API

api = Api(app, title='BGP Ranking API',
          description='API to query BGP Ranking.',
          version=pkg_resources.get_distribution('bgpranking').version)

api.add_namespace(generic_api)
