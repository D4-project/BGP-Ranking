#!/usr/bin/env python
# -*- coding: utf-8 -*-

try:
    import simplejson as json
except ImportError:
    import json

from flask import Flask, render_template, request, session, Response
from flask_bootstrap import Bootstrap

from bgpranking.querying import Querying
from datetime import date, timedelta
import pycountry
from collections import defaultdict

app = Flask(__name__)

app.secret_key = '\xeb\xfd\x1b\xee\xed<\xa5~\xd5H\x85\x00\xa5r\xae\x80t5@\xa2&>\x03S'

Bootstrap(app)
app.config['BOOTSTRAP_SERVE_LOCAL'] = True


def get_request_parameter(parameter):
    if request.method == 'POST':
        d = request.form
    elif request.method == 'GET':
        d = request.args

    return d.get(parameter, None)


def load_session():
    if request.method == 'POST':
        d = request.form
    elif request.method == 'GET':
        d = request.args

    if 'date' in d:
        session['date'] = d['date']
    if 'ipversion' in d:
        session['ipversion'] = d['ipversion']
    if 'source' in d:
        if '_all' in d.getlist('source'):
            session.pop('source', None)
        else:
            session['source'] = d.getlist('source')
    if 'asn' in d:
        session['asn'] = d['asn']
        session.pop('country', None)
    elif 'country' in d:
        if '_all' in d.getlist('country'):
            session.pop('country', None)
        else:
            session['country'] = d.getlist('country')
        session.pop('asn', None)
    set_default_date_session()


def set_default_date_session():
    if 'date' not in session:
        session['date'] = (date.today() - timedelta(days=1)).isoformat()


def get_country_codes():
    for c in pycountry.countries:
        yield c.alpha_2, c.name


@app.route('/', methods=['GET', 'POST'])
def index():
    load_session()
    q = Querying()
    sources = q.get_sources(date=session['date'])
    session.pop('asn', None)
    session.pop('country', None)
    ranks = q.asns_global_ranking(limit=100, **session)
    descriptions = [q.get_asn_descriptions(int(asn)) for asn, rank in ranks]
    r = zip(ranks, descriptions)
    return render_template('index.html', ranks=r, sources=sources, countries=get_country_codes(), **session)


@app.route('/asn', methods=['GET', 'POST'])
def asn_details():
    load_session()
    q = Querying()
    asn_descriptions = q.get_asn_descriptions(asn=session['asn'], all_descriptions=True)
    sources = q.get_sources(date=session['date'])
    ranks = q.asn_details(**session)
    prefix = get_request_parameter('prefix')
    if prefix:
        prefix_ips = q.get_prefix_ips(prefix=prefix, **session)
        prefix_ips = [(ip, sorted(sources)) for ip, sources in prefix_ips.items()]
        prefix_ips.sort(key=lambda entry: len(entry[1]), reverse=True)
    else:
        prefix_ips = []
    return render_template('asn.html', sources=sources, ranks=ranks, prefix_ips=prefix_ips, asn_descriptions=asn_descriptions, **session)


@app.route('/asn_description', methods=['POST'])
def asn_description():
    load_session()
    asn = None
    if request.form.get('asn'):
        asn = request.form.get('asn')
    elif session.get('asn'):
        asn = session.get('asn')
    else:
        to_return = {'error': 'asn required'}
    if asn:
        q = Querying()
        to_return = q.get_asn_descriptions(asn, session.get('all_descriptions'))
    return Response(json.dumps(to_return), mimetype='application/json')


@app.route('/asn_history', methods=['GET', 'POST'])
def asn_history():
    load_session()
    q = Querying()
    return Response(json.dumps(q.get_asn_history(**session)), mimetype='application/json')


@app.route('/country_history_callback', methods=['GET', 'POST'])
def country_history_callback():
    history_data = json.loads(request.data)
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
    return json.dumps(render_template('country_asn_map.html', to_display=to_display))


@app.route('/country_history', methods=['GET', 'POST'])
def country_history():
    load_session()
    q = Querying()
    return Response(json.dumps(q.country_history(**session)), mimetype='application/json')


@app.route('/country', methods=['GET', 'POST'])
def country():
    load_session()
    q = Querying()
    sources = q.get_sources(date=session['date'])
    return render_template('country.html', sources=sources, countries=get_country_codes(), **session)
