#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests

from bgpranking.default import get_homedir

d3js_version = '7'
bootstrap_select_version = "1.14.0-beta3"
jquery_version = "3.7.1"

if __name__ == '__main__':
    dest_dir = get_homedir() / 'website' / 'web' / 'static'

    d3 = requests.get(f'https://d3js.org/d3.v{d3js_version}.min.js')
    with (dest_dir / f'd3.v{d3js_version}.min.js').open('wb') as f:
        f.write(d3.content)
        print(f'Downloaded d3js v{d3js_version}.')

    bootstrap_select_js = requests.get(f'https://cdn.jsdelivr.net/npm/bootstrap-select@{bootstrap_select_version}/dist/js/bootstrap-select.min.js')
    with (dest_dir / 'bootstrap-select.min.js').open('wb') as f:
        f.write(bootstrap_select_js.content)
        print(f'Downloaded bootstrap_select js v{bootstrap_select_version}.')

    bootstrap_select_css = requests.get(f'https://cdn.jsdelivr.net/npm/bootstrap-select@{bootstrap_select_version}/dist/css/bootstrap-select.min.css')
    with (dest_dir / 'bootstrap-select.min.css').open('wb') as f:
        f.write(bootstrap_select_css.content)
        print(f'Downloaded bootstrap_select css v{bootstrap_select_version}.')

    jquery = requests.get(f'https://code.jquery.com/jquery-{jquery_version}.min.js')
    with (dest_dir / 'jquery.min.js').open('wb') as f:
        f.write(jquery.content)
        print(f'Downloaded jquery v{jquery_version}.')

    print('All 3rd party modules for the website were downloaded.')
