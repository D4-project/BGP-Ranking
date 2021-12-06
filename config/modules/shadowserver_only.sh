#!/bin/bash

set -e
set -x

find .  -maxdepth 1 -type f -name "*.json" ! -iname "shadowserver*.json" -delete
