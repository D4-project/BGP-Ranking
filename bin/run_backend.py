#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from bgpranking.libs.helpers import get_homedir, check_running
from subprocess import Popen
import time
from pathlib import Path

import argparse


def launch_cache(storage_directory: Path=None):
    if not storage_directory:
        storage_directory = get_homedir()
    if not check_running('cache'):
        Popen(["./run_redis.sh"], cwd=(storage_directory / 'cache'))


def shutdown_cache(storage_directory: Path=None):
    if not storage_directory:
        storage_directory = get_homedir()
    Popen(["./shutdown_redis.sh"], cwd=(storage_directory / 'cache'))


def launch_temp(storage_directory: Path=None):
    if not storage_directory:
        storage_directory = get_homedir()
    if not check_running('intake') and not check_running('prepare'):
        Popen(["./run_redis.sh"], cwd=(storage_directory / 'temp'))


def shutdown_temp(storage_directory: Path=None):
    if not storage_directory:
        storage_directory = get_homedir()
    Popen(["./shutdown_redis.sh"], cwd=(storage_directory / 'temp'))


def launch_storage(storage_directory: Path=None):
    if not storage_directory:
        storage_directory = get_homedir()
    if not check_running('storage'):
        Popen(["./run_ardb.sh"], cwd=(storage_directory / 'storage'))


def shutdown_storage(storage_directory: Path=None):
    if not storage_directory:
        storage_directory = get_homedir()
    Popen(["./shutdown_ardb.sh"], cwd=(storage_directory / 'storage'))


def launch_all():
    launch_cache()
    launch_temp()
    launch_storage()


def check_all(stop=False):
    backends = [['cache', False], ['storage', False],
                ['intake', False], ['prepare', False]]
    while True:
        for b in backends:
            try:
                b[1] = check_running(b[0])
            except Exception:
                b[1] = False
        if stop:
            if not any(b[1] for b in backends):
                break
        else:
            if all(b[1] for b in backends):
                break
        for b in backends:
            if not stop and not b[1]:
                print(f"Waiting on {b[0]}")
            if stop and b[1]:
                print(f"Waiting on {b[0]}")
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
