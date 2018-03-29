#!/usr/bin/env python
# -*- coding: utf-8 -*-

from bgpranking.libs.helpers import get_homedir
from subprocess import Popen
import time
from pathlib import Path
from redis import Redis

import argparse


def launch_cache(storage_directory: Path=None):
    if not storage_directory:
        storage_directory = get_homedir()
    Popen(["./run_redis.sh"], cwd=(storage_directory / 'cache'))


def shutdown_cache(storage_directory: Path=None):
    if not storage_directory:
        storage_directory = get_homedir()
    Popen(["./shutdown_redis.sh"], cwd=(storage_directory / 'cache'))


def launch_temp(storage_directory: Path=None):
    if not storage_directory:
        storage_directory = get_homedir()
    Popen(["./run_redis.sh"], cwd=(storage_directory / 'temp'))


def shutdown_temp(storage_directory: Path=None):
    if not storage_directory:
        storage_directory = get_homedir()
    Popen(["./shutdown_redis.sh"], cwd=(storage_directory / 'temp'))


def launch_storage(storage_directory: Path=None):
    if not storage_directory:
        storage_directory = get_homedir()
    Popen(["./run_ardb.sh"], cwd=(storage_directory / 'storage'))


def shutdown_storage(storage_directory: Path=None):
    if not storage_directory:
        storage_directory = get_homedir()
    Popen(["./shutdown_ardb.sh"], cwd=(storage_directory / 'storage'))


def check_running(host, port):
    r = Redis(host=host, port=port)
    return r.ping()


def launch_all():
    launch_cache()
    launch_temp()
    launch_storage()


def check_all(stop=False):
    backends = [['127.0.0.1', 6579, False], ['127.0.0.1', 6580, False],
                ['127.0.0.1', 6581, False], ['127.0.0.1', 6582, False],
                ['127.0.0.1', 16579, False]]
    while True:
        for b in backends:
            try:
                b[2] = check_running(b[0], b[1])
            except Exception:
                b[2] = False
        if stop:
            if not any(b[2] for b in backends):
                break
        else:
            if all(b[2] for b in backends):
                break
        for b in backends:
            if not stop and not b[2]:
                print('Waiting on {}:{}'.format(b[0], b[1]))
            if stop and b[2]:
                print('Waiting on {}:{}'.format(b[0], b[1]))
        time.sleep(1)


def stop_all():
    shutdown_cache()
    shutdown_temp()
    shutdown_storage()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Manage backend DBs.')
    parser.add_argument("--start", action='store_true', default=False, help="Start all")
    parser.add_argument("--stop", action='store_true', default=False, help="Stop all")
    parser.add_argument("--status", action='store_true', default=True, help="Show status")
    args = parser.parse_args()

    if args.start:
        launch_all()
    if args.stop:
        stop_all()
    if not args.stop and args.status:
        check_all()
