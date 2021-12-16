#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pkg_resources

from collections import defaultdict
from datetime import date, timedelta
from typing import Dict, Any, Tuple, List, Optional

from flask import Flask, render_template, request, session, redirect, url_for
from flask_bootstrap import Bootstrap  # type: ignore
from flask_restx import Api  # type: ignore

from bgpranking.bgpranking import BGPRanking
from bgpranking.helpers import get_ipasn

from .genericapi import api as generic_api
from .helpers import get_secret_key, load_session, get_country_codes
from .proxied import ReverseProxied

app = Flask(__name__)

app.wsgi_app = ReverseProxied(app.wsgi_app)  # type: ignore

app.config['SECRET_KEY'] = get_secret_key()

Bootstrap(app)
app.config['BOOTSTRAP_SERVE_LOCAL'] = True

bgpranking = BGPRanking()


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

# Query API

api = Api(app, title='BGP Ranking API',
          description='API to query BGP Ranking.',
          doc='/doc/',
          version=pkg_resources.get_distribution('bgpranking').version)

api.add_namespace(generic_api)
