#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

import requests

from pyipasnhistory import IPASNHistory

from .default import get_homedir, get_config, ThirdPartyUnreachable, safe_create_dir


@lru_cache(64)
def get_data_dir() -> Path:
    capture_dir = get_homedir() / 'rawdata'
    safe_create_dir(capture_dir)
    return capture_dir


@lru_cache(64)
def get_modules_dir() -> Path:
    modules_dir = get_homedir() / 'config' / 'modules'
    safe_create_dir(modules_dir)
    return modules_dir


@lru_cache(64)
def get_modules() -> List[Path]:
    return [modulepath for modulepath in get_modules_dir().glob('*.json')]


@lru_cache(64)
def load_all_modules_configs() -> Dict[str, Dict]:
    configs = {}
    for p in get_modules():
        with p.open() as f:
            j = json.load(f)
            configs[f"{j['vendor']}-{j['name']}"] = j
    return configs


def get_ipasn():
    ipasnhistory_url = get_config('generic', 'ipasnhistory_url')
    ipasn = IPASNHistory(ipasnhistory_url)
    if not ipasn.is_up:
        raise ThirdPartyUnreachable(f"Unable to reach IPASNHistory on {ipasnhistory_url}")
    return ipasn


def sanity_check_ipasn(ipasn):
    try:
        meta = ipasn.meta()
    except requests.exceptions.ConnectionError:
        return False, "IP ASN History is not reachable, try again later."

    if 'error' in meta:
        raise ThirdPartyUnreachable(f'IP ASN History has a problem: {meta["error"]}')

    v4_percent = meta['cached_dates']['caida']['v4']['percent']
    v6_percent = meta['cached_dates']['caida']['v6']['percent']
    if v4_percent < 90 or v6_percent < 90:  # (this way it works if we only load 10 days)
        # Try again later.
        return False, f"IP ASN History is not ready: v4 {v4_percent}% / v6 {v6_percent}% loaded"
    return True, f"IP ASN History is ready: v4 {v4_percent}% / v6 {v6_percent}% loaded"
