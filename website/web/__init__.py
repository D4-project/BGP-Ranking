#!/usr/bin/env python
# -*- coding: utf-8 -*-

from urllib.parse import urljoin
try:
    import simplejson as json
except ImportError:
    import json

import os

import requests

from flask import Flask, render_template, request, session, Response, redirect, url_for
from flask_bootstrap import Bootstrap

from bgpranking.querying import Querying
from bgpranking.libs.exceptions import MissingConfigEntry
from bgpranking.libs.helpers import load_general_config, get_homedir, get_ipasn
from datetime import date, timedelta
import pycountry
from collections import defaultdict

app = Flask(__name__)

secret_file_path = get_homedir() / 'website' / 'secret_key'

if not secret_file_path.exists() or secret_file_path.stat().st_size < 64:
    with open(secret_file_path, 'wb') as f:
        f.write(os.urandom(64))

with open(secret_file_path, 'rb') as f:
    app.config['SECRET_KEY'] = f.read()

Bootstrap(app)
app.config['BOOTSTRAP_SERVE_LOCAL'] = True


# ############# Helpers #############

def load_session():
    if request.method == 'POST':
        d = request.form
    elif request.method == 'GET':
        d = request.args

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
    q = Querying()
    sources = q.get_sources(date=session['date'])['response']
    session.pop('asn', None)
    session.pop('country', None)
    ranks = q.asns_global_ranking(limit=100, **session)['response']
    r = [(asn, rank, q.get_asn_descriptions(int(asn))['response']) for asn, rank in ranks]
    return render_template('index.html', ranks=r, sources=sources, countries=get_country_codes(), **session)


@app.route('/asn', methods=['GET', 'POST'])
def asn_details():
    load_session()
    q = Querying()
    if 'asn' not in session:
        return redirect(url_for('/'))
    asn_descriptions = q.get_asn_descriptions(asn=session['asn'], all_descriptions=True)['response']
    sources = q.get_sources(date=session['date'])['response']
    prefix = session.pop('prefix', None)
    ranks = q.asn_details(**session)['response']
    if prefix:
        prefix_ips = q.get_prefix_ips(prefix=prefix, **session)['response']
        prefix_ips = [(ip, sorted(sources)) for ip, sources in prefix_ips.items()]
        prefix_ips.sort(key=lambda entry: len(entry[1]), reverse=True)
    else:
        prefix_ips = []
    return render_template('asn.html', sources=sources, ranks=ranks,
                           prefix_ips=prefix_ips, asn_descriptions=asn_descriptions, **session)


@app.route('/country', methods=['GET', 'POST'])
def country():
    load_session()
    q = Querying()
    sources = q.get_sources(date=session['date'])['response']
    return render_template('country.html', sources=sources, countries=get_country_codes(), **session)


@app.route('/country_history_callback', methods=['GET', 'POST'])
def country_history_callback():
    history_data = request.get_json(force=True)
    to_display = []
    mapping = defaultdict(dict)
    dates = []
    all_asns = set([])
    for country, data in history_data.items():
        for d, r_sum, details in data:
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
    d = None
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
    q = Querying()
    response = ipasn.query(first=(date.today() - timedelta(days=60)).isoformat(),
                           aggregate=True, ip=ip)
    for r in response['response']:
        r['asn_descriptions'] = []
        asn_descriptions = q.get_asn_descriptions(asn=r['asn'], all_descriptions=True)['response']
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
    config, general_config_file = load_general_config()
    if 'ipasnhistory_url' not in config:
        raise MissingConfigEntry(f'"ipasnhistory_url" is missing in {general_config_file}.')

    path_for_ipasnhistory = request.full_path.replace('/ipasn_history', '')
    if '/?' in path_for_ipasnhistory:
        path_for_ipasnhistory = path_for_ipasnhistory.replace('/?', '/ip?')
    print(path_for_ipasnhistory)
    proxied_url = urljoin(config['ipasnhistory_url'], path_for_ipasnhistory)
    print(proxied_url)
    if request.method in ['GET', 'HEAD']:
        to_return = requests.get(proxied_url).json()
    elif request.method == 'POST':
        to_return = requests.post(proxied_url, data=request.data).json()
    return Response(json.dumps(to_return), mimetype='application/json')


@app.route('/json/asn', methods=['POST'])
def json_asn():
    # TODO
    # * Filter on date => if only returning one descr, return the desription at that date
    query = request.get_json(force=True)
    to_return = {'meta': query, 'response': {}}
    if 'asn' not in query:
        to_return['error'] = f'You need to pass an asn - {query}'
        return Response(json.dumps(to_return), mimetype='application/json')

    q = Querying()
    asn_description_query = {'asn': query['asn']}
    if 'all_descriptions' in query:
        asn_description_query['all_descriptions'] = query['all_descriptions']
    to_return['response']['asn_description'] = q.get_asn_descriptions(**asn_description_query)['response']

    asn_rank_query = {'asn': query['asn']}
    if 'date' in query:
        asn_rank_query['date'] = query['date']
    if 'source' in query:
        asn_rank_query['source'] = query['source']
    else:
        asn_rank_query['with_position'] = True
    if 'ipversion' in query:
        asn_rank_query['ipversion'] = query['ipversion']

    to_return['response']['ranking'] = q.asn_rank(**asn_rank_query)['response']
    return Response(json.dumps(to_return), mimetype='application/json')


@app.route('/json/asn_descriptions', methods=['POST'])
def asn_description():
    query = request.get_json(force=True)
    to_return = {'meta': query, 'response': {}}
    if 'asn' not in query:
        to_return['error'] = f'You need to pass an asn - {query}'
        return Response(json.dumps(to_return), mimetype='application/json')

    q = Querying()
    to_return['response']['asn_descriptions'] = q.get_asn_descriptions(**query)['response']
    return Response(json.dumps(to_return), mimetype='application/json')


@app.route('/json/asn_history', methods=['GET', 'POST'])
def asn_history():
    q = Querying()
    if request.method == 'GET':
        load_session()
        if 'asn' in session:
            return Response(json.dumps(q.get_asn_history(**session)), mimetype='application/json')

    query = request.get_json(force=True)
    to_return = {'meta': query, 'response': {}}
    if 'asn' not in query:
        to_return['error'] = f'You need to pass an asn - {query}'
        return Response(json.dumps(to_return), mimetype='application/json')

    to_return['response']['asn_history'] = q.get_asn_history(**query)['response']
    return Response(json.dumps(to_return), mimetype='application/json')


@app.route('/json/country_history', methods=['GET', 'POST'])
def country_history():
    q = Querying()
    if request.method == 'GET':
        load_session()
        return Response(json.dumps(q.country_history(**session)), mimetype='application/json')

    query = request.get_json(force=True)
    to_return = {'meta': query, 'response': {}}
    to_return['response']['country_history'] = q.country_history(**query)['response']
    return Response(json.dumps(to_return), mimetype='application/json')


@app.route('/json/asns_global_ranking', methods=['POST'])
def json_asns_global_ranking():
    query = request.get_json(force=True)
    to_return = {'meta': query, 'response': {}}
    q = Querying()
    to_return['response'] = q.asns_global_ranking(**query)['response']
    return Response(json.dumps(to_return), mimetype='application/json')

# ############# Json outputs #############
