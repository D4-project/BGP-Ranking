#!/bin/bash

# set -e
set -x

../../redis/src/redis-cli -s ./intake.sock shutdown
../../redis/src/redis-cli -s ./prepare.sock shutdown
