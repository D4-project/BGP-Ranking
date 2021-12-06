#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pkg_resources

from flask import Flask
from flask_restx import Api, Resource  # type: ignore

from bgpranking.bgpranking import BGPRanking

from .helpers import get_secret_key
from .proxied import ReverseProxied

app: Flask = Flask(__name__)

app.wsgi_app = ReverseProxied(app.wsgi_app)  # type: ignore

app.config['SECRET_KEY'] = get_secret_key()

api = Api(app, title='BGP Ranking API',
          description='API to query BGP Ranking.',
          version=pkg_resources.get_distribution('bgpranking').version)

bgpranking: BGPRanking = BGPRanking()


@api.route('/redis_up')
@api.doc(description='Check if redis is up and running')
class RedisUp(Resource):

    def get(self):
        return bgpranking.check_redis_up()
