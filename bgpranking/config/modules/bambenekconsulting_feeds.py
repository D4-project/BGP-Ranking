#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import re
import requests
from bs4 import BeautifulSoup


def get_paths():
    root = 'http://osint.bambenekconsulting.com/feeds/'
    r = requests.get(root)
    soup = BeautifulSoup(r.text, 'html.parser')

    to_return = []
    for entry in soup.find_all('p'):
        name = entry.b.string
        if name:
            for link in entry.find_all('a'):
                if link.get('href').endswith('iplist.txt'):
                    path = link.get('href')
                    if link.get('href').endswith('nsiplist.txt'):
                        name = f'{name}_NS'
                    to_return.append((name, f'{root}{path}'))
    return to_return


def make_config(entry):
    name = entry[0].replace(' ', '_')
    config = {'url': entry[1], 'name': name, 'vendor': 'bambenekconsulting', 'impact': 3}
    filename = re.sub('[^0-9a-zA-Z]+', '_', name)
    with open(f'bambenekconsulting_{filename}.json', 'w') as f:
        json.dump(config, f, indent=2)


if __name__ == '__main__':

    for entry in get_paths():
        make_config(entry)
