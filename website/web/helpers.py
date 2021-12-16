#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os

from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

import pycountry  # type: ignore

from flask import request, session

from bgpranking.default import get_homedir


def src_request_ip(request) -> str:
    # NOTE: X-Real-IP is the IP passed by the reverse proxy in the headers.
    real_ip = request.headers.get('X-Real-IP')
    if not real_ip:
        real_ip = request.remote_addr
    return real_ip


@lru_cache(64)
def get_secret_key() -> bytes:
    secret_file_path: Path = get_homedir() / 'secret_key'
    if not secret_file_path.exists() or secret_file_path.stat().st_size < 64:
        if not secret_file_path.exists() or secret_file_path.stat().st_size < 64:
            with secret_file_path.open('wb') as f:
                f.write(os.urandom(64))
    with secret_file_path.open('rb') as f:
        return f.read()


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
