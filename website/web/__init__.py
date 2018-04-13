#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask, render_template, request, session
from flask_bootstrap import Bootstrap

from bgpranking.querying import Querying
from pathlib import Path
from datetime import date, timedelta


app = Flask(__name__)

app.secret_key = '\xeb\xfd\x1b\xee\xed<\xa5~\xd5H\x85\x00\xa5r\xae\x80t5@\xa2&>\x03S'

Bootstrap(app)
app.config['BOOTSTRAP_SERVE_LOCAL'] = True

jquery_js = Path('static', 'jquery-ui.js')
jquery_css = Path('static', 'jquery-ui.css')


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
    ranks = q.asns_global_ranking(limit=-1, **session)
    descriptions = [q.get_asn_descriptions(int(asn)) for asn, rank in ranks]
    r = zip(ranks, descriptions)
    return render_template('index.html', ranks=r, sources=sources, **session)


@app.route('/asn', methods=['GET', 'POST'])
def asn_details():
    load_session()
    q = Querying()
    ranks = q.asn_details(**session)
    return render_template('asn.html', ranks=ranks, **session)
