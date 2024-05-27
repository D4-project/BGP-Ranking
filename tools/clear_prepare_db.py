#!/usr/bin/env python3

import uuid

from redis import Redis
from bgpranking.default import get_socket_path

redis_sanitized = Redis(unix_socket_path=get_socket_path('prepare'), db=0, decode_responses=True)
to_delete = []
for name in redis_sanitized.scan_iter(_type='HASH', count=100):
    try:
        uuid.UUID(name)
    except Exception as e:
        continue
    if not redis_sanitized.sismember('to_insert', name):
        to_delete.append(name)
    if len(to_delete) >= 100000:
        redis_sanitized.delete(*to_delete)
        to_delete = []
if to_delete: 
    redis_sanitized.delete(*to_delete)
