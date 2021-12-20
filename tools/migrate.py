#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime
from typing import Set

from redis import Redis

redis_src = Redis(unix_socket_path='../storage/storage.sock', db=0)
redis_dst = Redis('127.0.0.1', 5188)

chunk_size = 100000


def process_chunk(src: Redis, dst: Redis, keys: Set[str]):
    src_pipeline = src.pipeline()
    [src_pipeline.type(key) for key in keys]
    to_process = {key: key_type for key, key_type in zip(keys, src_pipeline.execute())}

    src_pipeline = src.pipeline()
    for key, key_type in to_process.items():
        if key_type == b"string":
            src_pipeline.get(key)
        elif key_type == b"list":
            raise Exception(f'Lists should not be used: {key}.')
        elif key_type == b"set":
            src_pipeline.smembers(key)
        elif key_type == b"zset":
            src_pipeline.zrangebyscore(key, '-Inf', '+Inf', withscores=True)
        elif key_type == b"hash":
            src_pipeline.hgetall(key)
        else:
            raise Exception(f'{key_type} not supported {key}.')

    dest_pipeline = dst.pipeline()
    for key, content in zip(to_process.keys(), src_pipeline.execute()):
        if to_process[key] == b"string":
            dest_pipeline.set(key, content)
        elif to_process[key] == b"set":
            dest_pipeline.sadd(key, *content)
        elif to_process[key] == b"zset":
            dest_pipeline.zadd(key, {value: rank for value, rank in content})
        elif to_process[key] == b"hash":
            dest_pipeline.hmset(key, content)

    dest_pipeline.execute()


def migrate(src: Redis, dst: Redis):
    keys = set()
    pos = 0
    for key in src.scan_iter(count=chunk_size, match='2017*'):
        keys.add(key)

        if len(keys) == chunk_size:
            process_chunk(src, dst, keys)
            pos += len(keys)
            print(f'{datetime.now()} - {pos} keys done.')
            keys = set()

    # migrate remaining keys
    process_chunk(src, dst, keys)
    pos += len(keys)
    print(f'{datetime.now()} - {pos} keys done.')


if __name__ == '__main__':
    migrate(redis_src, redis_dst)
