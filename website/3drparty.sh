#!/bin/bash

set -e
set -x

mkdir -p web/static/

wget https://d3js.org/d3.v5.js -O web/static/d3.v5.js

BOOTSTRAP_SELECT="1.12.4"

wget https://cdnjs.cloudflare.com/ajax/libs/bootstrap-select/${BOOTSTRAP_SELECT}/css/bootstrap-select.min.css -O web/static/bootstrap-select.min.css
wget https://cdnjs.cloudflare.com/ajax/libs/bootstrap-select/${BOOTSTRAP_SELECT}/js/bootstrap-select.min.js -O web/static/bootstrap-select.min.js
