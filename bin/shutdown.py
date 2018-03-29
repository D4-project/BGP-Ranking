#!/usr/bin/env python
# -*- coding: utf-8 -*-

from bgpranking.libs.helpers import is_running
import time
from redis import StrictRedis

if __name__ == '__main__':
    r = StrictRedis(host='localhost', port=6582, db=1, decode_responses=True)
    r.set('shutdown', 1)
    while True:
        running = is_running()
        print(running)
        if not running:
            break
        time.sleep(10)
