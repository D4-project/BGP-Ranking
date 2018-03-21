#!/bin/bash

set -e
set -x

../../redis/src/redis-server ./6579.conf
../../redis/src/redis-server ./6580.conf
