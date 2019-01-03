#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path
from .exceptions import CreateDirectoryException, MissingEnv, MissingConfigFile, MissingConfigEntry, ThirdPartyUnreachable
from redis import StrictRedis
from redis.exceptions import ConnectionError
from datetime import datetime, timedelta
import time
try:
    import simplejson as json
except ImportError:
    import json
from pyipasnhistory import IPASNHistory


def load_config_files(config_dir: Path=None) -> dict:
    if not config_dir:
        config_dir = get_config_path()
    modules_config = config_dir / 'modules'
    modules_paths = [modulepath for modulepath in modules_config.glob('*.json')]
    configs = {}
    for p in modules_paths:
        with open(p, 'r') as f:
            j = json.load(f)
            configs[f"{j['vendor']}-{j['name']}"] = j
    return configs


def get_config_path():
    if Path('bgpranking', 'config').exists():
        # Running from the repository
        return Path('bgpranking', 'config')
    return Path(sys.modules['bgpranking'].__file__).parent / 'config'


def get_list_storage_path():
    if not os.environ.get('VIRTUAL_ENV'):
        raise MissingEnv("VIRTUAL_ENV is missing. This project really wants to run from a virtual envoronment.")
    return Path(os.environ['VIRTUAL_ENV'])


def get_homedir():
    if not os.environ.get('BGPRANKING_HOME'):
        guessed_home = Path(__file__).resolve().parent.parent.parent
        raise MissingEnv(f"BGPRANKING_HOME is missing. \
Run the following command (assuming you run the code from the clonned repository):\
    export BGPRANKING_HOME='{guessed_home}'")
    return Path(os.environ['BGPRANKING_HOME'])


def safe_create_dir(to_create: Path):
    if to_create.exists() and not to_create.is_dir():
        raise CreateDirectoryException(f'The path {to_create} already exists and is not a directory')
    os.makedirs(to_create, exist_ok=True)


def set_running(name: str):
    r = StrictRedis(unix_socket_path=get_socket_path('cache'), db=1, decode_responses=True)
    r.hset('running', name, 1)


def unset_running(name: str):
    r = StrictRedis(unix_socket_path=get_socket_path('cache'), db=1, decode_responses=True)
    r.hdel('running', name)


def is_running():
    r = StrictRedis(unix_socket_path=get_socket_path('cache'), db=1, decode_responses=True)
    return r.hgetall('running')


def get_socket_path(name: str):
    mapping = {
        'cache': Path('cache', 'cache.sock'),
        'storage': Path('storage', 'storage.sock'),
        'intake': Path('temp', 'intake.sock'),
        'prepare': Path('temp', 'prepare.sock'),
    }
    return str(get_homedir() / mapping[name])


def load_general_config():
    general_config_file = get_config_path() / 'bgpranking.json'
    if not general_config_file.exists():
        raise MissingConfigFile(f'The general configuration file ({general_config_file}) does not exists.')
    with open(general_config_file) as f:
        config = json.load(f)
    return config, general_config_file


def get_ipasn():
    config, general_config_file = load_general_config()
    if 'ipasnhistory_url' not in config:
        raise MissingConfigEntry(f'"ipasnhistory_url" is missing in {general_config_file}.')
    ipasn = IPASNHistory(config['ipasnhistory_url'])
    if not ipasn.is_up:
        raise ThirdPartyUnreachable(f"Unable to reach IPASNHistory on {config['ipasnhistory_url']}")
    return ipasn


def sanity_check_ipasn(ipasn):
    meta = ipasn.meta()
    if 'error' in meta:
        raise ThirdPartyUnreachable(f'IP ASN History has a problem: meta["error"]')

    v4_percent = meta['cached_dates']['caida']['v4']['percent']
    v6_percent = meta['cached_dates']['caida']['v6']['percent']
    if v4_percent < 90 or v6_percent < 90:  # (this way it works if we only load 10 days)
        # Try again later.
        return False, f"IP ASN History is not ready: v4 {v4_percent}% / v6 {v6_percent}% loaded"
    return True, f"IP ASN History is ready: v4 {v4_percent}% / v6 {v6_percent}% loaded"


def check_running(name: str):
    socket_path = get_socket_path(name)
    try:
        r = StrictRedis(unix_socket_path=socket_path)
        return r.ping()
    except ConnectionError:
        return False


def shutdown_requested():
    try:
        r = StrictRedis(unix_socket_path=get_socket_path('cache'), db=1, decode_responses=True)
        return r.exists('shutdown')
    except ConnectionRefusedError:
        return True
    except ConnectionError:
        return True


def long_sleep(sleep_in_sec: int, shutdown_check: int=10):
    sleep_until = datetime.now() + timedelta(seconds=sleep_in_sec)
    while sleep_until > datetime.now():
        time.sleep(shutdown_check)
        if shutdown_requested():
            return False
    return True
