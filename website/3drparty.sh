#!/bin/bash

set -e
set -x

wget https://code.jquery.com/ui/1.12.1/jquery-ui.js -O web/static/jquery-ui.js
wget https://code.jquery.com/ui/1.12.1/themes/base/jquery-ui.css -O web/static/jquery-ui.css
