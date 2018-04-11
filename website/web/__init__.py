#!/usr/bin/env python
# -*- coding: utf-8 -*-


from flask import Flask, render_template
from flask_bootstrap import Bootstrap

from bgpranking.querying import Querying

app = Flask(__name__)

Bootstrap(app)
app.config['BOOTSTRAP_SERVE_LOCAL'] = True

app.debug = True


@app.route('/', methods=['GET'])
def index():
    q = Querying()
    ranks = q.asns_global_ranking(limit=-1)
    return render_template('index.html', ranks=ranks)


@app.route('/asn/<int:asn>', methods=['GET'])
def asn_details(asn):
    q = Querying()
    ranks = q.asn_details(asn)
    return render_template('asn.html', asn=asn, ranks=ranks)
