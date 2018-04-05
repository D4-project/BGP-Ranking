#!/bin/bash

# set -e
set -x

../../redis/src/redis-cli -s ./ris.sock shutdown
../../redis/src/redis-cli -s ./prefixes.sock shutdown
