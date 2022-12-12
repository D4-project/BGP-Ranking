#!/usr/bin/env python3

import uuid

from redis import Redis
from bgpranking.default import get_socket_path

redis_sanitized = Redis(unix_socket_path=get_socket_path('prepare'), db=0, decode_responses=True)

while name := redis_sanitized.scan_iter(_type='HASH', count=10):
    try:
        uuid.uuid(name)
    except Exception:
        pass
    if not redis_sanitized.sismember('to_insert'):
        print(name)
