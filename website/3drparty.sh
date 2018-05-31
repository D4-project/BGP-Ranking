#!/bin/bash

set -e
set -x

mkdir -p web/static/

wget https://d3js.org/d3.v5.js -O web/static/d3.v5.js
