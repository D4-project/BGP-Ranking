#!/bin/bash

set -e
set -x

if [ -f  ../../valkey/src/valkey-server ]; then
    ../../valkey/src/redis-server ./intake.conf
    ../../valkey/src/redis-server ./prepare.conf
elif [ -f ../../redis/src/redis-server ]; then
    ../../redis/src/redis-server ./intake.conf
    ../../redis/src/redis-server ./prepare.conf
else
    echo "Warning: using system redis-server. Valkey-server or redis-server from source is recommended." >&2
    /usr/bin/redis-server ./intake.conf
    /usr/bin/redis-server ./prepare.conf
fi
