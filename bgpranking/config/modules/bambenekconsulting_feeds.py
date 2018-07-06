#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import re
import requests
from bs4 import BeautifulSoup

from pymispgalaxies import Clusters


def find_tags(name):
    if '/' in name:
        to_search = name.split('/')
    else:
        to_search = [name]
    tags = []
    for name in to_search:
        responses = c.search(name.strip(), return_tags=True)
        for _, t in responses:
            tags += t
    return list(set(tags))


def get_paths():
    root = 'http://osint.bambenekconsulting.com'
    r = requests.get(f'{root}/feeds/')
    soup = BeautifulSoup(r.text, 'html.parser')
    to_return = []
    for entry in soup.find_all('p'):
        name = entry.b.string
        tags = find_tags(name)
        if name:
            for link in entry.find_all('a'):
                if link.get('href').endswith('iplist.txt'):
                    path = link.get('href')
                    if link.get('href').endswith('nsiplist.txt'):
                        name = f'{name}_NS'
                    to_return.append((name, f'{root}{path}', tags))
    return to_return


def make_config(entry):
    name = entry[0].replace(' ', '_')
    config = {'url': entry[1], 'name': name, 'vendor': 'bambenekconsulting',
              'impact': 3, 'parser': '.parsers.bambenekconsulting'}
    if len(entry) >= 3 and entry[2]:
        config['tags'] = entry[2]
    else:
        print('No tags:', name)
    filename = re.sub('[^0-9a-zA-Z]+', '_', name)
    with open(f'bambenekconsulting_{filename}.json', 'w') as f:
        json.dump(config, f, indent=2)


if __name__ == '__main__':
    c = Clusters()

    for entry in get_paths():
        make_config(entry)
