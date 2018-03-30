#!/usr/bin/env python
# -*- coding: utf-8 -*-

from subprocess import Popen
from bgpranking.libs.helpers import get_homedir


if __name__ == '__main__':
    # Just fail if the env isn't set.
    get_homedir()
    p = Popen(['run_backend.py', '--start'])
    p.wait()
    Popen(['loadprefixes.py'])
    Popen(['rislookup.py'])
    Popen(['fetcher.py'])
    Popen(['parser.py'])
    Popen(['sanitizer.py'])
    Popen(['dbinsert.py'])
