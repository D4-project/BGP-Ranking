#!/bin/bash

# set -e
set -x

../../redis/src/redis-cli -p 6579 shutdown
../../redis/src/redis-cli -p 6580 shutdown
