#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json

from flask import Flask, render_template, request, session
from flask_bootstrap import Bootstrap

from bgpranking.querying import Querying
from datetime import date, timedelta

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
        session['source'] = d['source']
    if 'asn' in d:
        session['asn'] = d['asn']
    set_default_date_session()


def set_default_date_session():
    if 'date' not in session:
        session['date'] = (date.today() - timedelta(days=1)).isoformat()


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
    return render_template('index.html', ranks=r, sources=sources, **session)


@app.route('/asn', methods=['GET', 'POST'])
def asn_details():
    load_session()
    session.pop('country', None)
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


@app.route('/asn_history', methods=['GET', 'POST'])
def asn_history():
    load_session()
    session.pop('country', None)
    q = Querying()
    return json.dumps(q.get_asn_history(**session))


@app.route('/country_history', methods=['GET', 'POST'])
def country_history():
    load_session()
    q = Querying()
    return json.dumps(q.country_history(**session))


@app.route('/country', methods=['GET', 'POST'])
def country():
    load_session()
    q = Querying()
    sources = q.get_sources(date=session['date'])
    session.pop('asn', None)
    return render_template('country.html', sources=sources, **session)
