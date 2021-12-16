#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from subprocess import Popen, run

from bgpranking.default import get_homedir


def main():
    # Just fail if the env isn't set.
    get_homedir()
    print('Start backend (redis)...')
    p = run(['run_backend', '--start'])
    p.check_returncode()
    print('done.')
    Popen(['fetcher'])
    # Popen(['ssfetcher'])
    Popen(['parser'])
    Popen(['sanitizer'])
    Popen(['dbinsert'])
    Popen(['ranking'])
    Popen(['asn_descriptions'])
    print('Start website...')
    Popen(['start_website'])
    print('done.')


if __name__ == '__main__':
    main()
