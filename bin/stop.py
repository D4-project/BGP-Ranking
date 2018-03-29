#!/usr/bin/env python
# -*- coding: utf-8 -*-

from subprocess import Popen


if __name__ == '__main__':
    p = Popen(['shutdown.py'])
    p.wait()
    Popen(['run_backend.py', '--stop'])
