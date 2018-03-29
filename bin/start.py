#!/usr/bin/env python
# -*- coding: utf-8 -*-

from subprocess import Popen


if __name__ == '__main__':
    p = Popen(['run_backend.py', '--start'])
    p.wait()
    Popen(['loadprefixes.py'])
    Popen(['rislookup.py'])
    Popen(['fetcher.py'])
    Popen(['parser.py'])
    Popen(['sanitizer.py'])
    Popen(['dbinsert.py'])
