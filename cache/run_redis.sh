#!/bin/bash

set -e
set -x

../../redis/src/redis-server ./ris.conf
../../redis/src/redis-server ./prefixes.conf
