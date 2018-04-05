#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
from pathlib import Path
from .exceptions import CreateDirectoryException, MissingEnv
from redis import StrictRedis
from redis.exceptions import ConnectionError
from datetime import datetime, timedelta
import time


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
        raise MissingEnv("BGPRANKING_HOME is missing. Run the following from the home directory of the repository: export BGPRANKING_HOME='./'")
    return Path(os.environ['BGPRANKING_HOME'])


def safe_create_dir(to_create: Path):
    if to_create.exists() and not to_create.is_dir():
        raise CreateDirectoryException('The path {} already exists and is not a directory'.format(to_create))
    os.makedirs(to_create, exist_ok=True)


def set_running(name: str):
    r = StrictRedis(unix_socket_path=get_socket_path('prefixes'), db=1, decode_responses=True)
    r.hset('running', name, 1)


def unset_running(name: str):
    r = StrictRedis(unix_socket_path=get_socket_path('prefixes'), db=1, decode_responses=True)
    r.hdel('running', name)


def is_running():
    r = StrictRedis(unix_socket_path=get_socket_path('prefixes'), db=1, decode_responses=True)
    return r.hgetall('running')


def get_socket_path(name: str):
    mapping = {
        'ris': Path('cache', 'ris.sock'),
        'prefixes': Path('cache', 'prefixes.sock'),
        'storage': Path('storage', 'storage.sock'),
        'intake': Path('temp', 'intake.sock'),
        'prepare': Path('temp', 'prepare.sock'),
    }
    return str(get_homedir() / mapping[name])


def check_running(name: str):
    socket_path = get_socket_path(name)
    try:
        r = StrictRedis(unix_socket_path=socket_path)
        return r.ping()
    except ConnectionError:
        return False


def shutdown_requested():
    try:
        r = StrictRedis(unix_socket_path=get_socket_path('prefixes'), db=1, decode_responses=True)
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
