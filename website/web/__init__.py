#!/usr/bin/env python
# -*- coding: utf-8 -*-

from flask import Flask, render_template, request
from flask_bootstrap import Bootstrap
from flask_datepicker import datepicker

from bgpranking.querying import Querying

app = Flask(__name__)

Bootstrap(app)
app.config['BOOTSTRAP_SERVE_LOCAL'] = True
datepicker(app=app, local=['static/jquery-ui.js', 'static/jquery-ui.css'])

app.debug = True


@app.route('/', methods=['GET'])
def index():
    q = Querying()
    ranks = q.asns_global_ranking(limit=-1)
    return render_template('index.html', ranks=ranks)


@app.route('/asn', methods=['GET', 'POST'])
def asn_details():
    q = Querying()
    if request.method == 'POST':
        asn = request.form['asn']
    if request.method == 'GET':
        asn = request.args['asn']
    ranks = q.asn_details(asn)
    return render_template('asn.html', asn=asn, ranks=ranks)
