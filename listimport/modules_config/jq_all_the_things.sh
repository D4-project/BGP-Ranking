#!/bin/bash

set -e
set -x

# Seeds sponge, from moreutils

for dir in ./*.json
do
    cat ${dir} | jq . | sponge ${dir}
done
