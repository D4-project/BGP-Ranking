#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from subprocess import Popen
from bgpranking.libs.helpers import get_homedir


if __name__ == '__main__':
    # Just fail if the env isn't set.
    get_homedir()
    p = Popen(['run_backend.py', '--start'])
    p.wait()
    Popen(['fetcher.py'])
    Popen(['ssfetcher.py'])
    Popen(['parser.py'])
    Popen(['sanitizer.py'])
    Popen(['dbinsert.py'])
    Popen(['ranking.py'])
    Popen(['asn_descriptions.py'])
