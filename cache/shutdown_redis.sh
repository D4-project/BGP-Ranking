#!/bin/bash

# set -e
set -x

../../redis/src/redis-cli -p 6581 shutdown
../../redis/src/redis-cli -p 6582 shutdown
