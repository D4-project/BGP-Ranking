#!/bin/bash

set -e
set -x

../../redis/src/redis-server ./intake.conf
../../redis/src/redis-server ./prepare.conf
