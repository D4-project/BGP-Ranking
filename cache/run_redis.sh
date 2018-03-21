#!/bin/bash

set -e
set -x

../../redis/src/redis-server ./6581.conf
../../redis/src/redis-server ./6582.conf
