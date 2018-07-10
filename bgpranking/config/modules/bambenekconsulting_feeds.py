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
    if not tags:
        print('No tags for', name)
    return list(set(tags))


def get_paths():
    root = 'http://osint.bambenekconsulting.com'
    r = requests.get(f'{root}/feeds/')
    soup = BeautifulSoup(r.text, 'html.parser')
    for entry in soup.find_all('p'):
        config = {'vendor': 'bambenekconsulting', 'parser': '.parsers.bambenekconsulting'}
        if 'FP Risk: Low' in str(entry):
            tags = ['false-positive:risk="low"']
            config['impact'] = 5
        if 'FP Risk: Medium' in str(entry):
            tags = ['false-positive:risk="medium"']
            config['impact'] = 3
        if 'FP Risk: High' in str(entry):
            tags = ['false-positive:risk="high"']
            config['impact'] = 1
        name = entry.b.string
        tags += find_tags(name)
        if name:
            for link in entry.find_all('a'):
                if link.get('href').endswith('iplist.txt'):
                    path = link.get('href')
                    if link.get('href').endswith('nsiplist.txt'):
                        name = f'{name}_NS'
                    config['name'] = name.replace(' ', '_')
                    config['url'] = f'{root}{path}'
                    config['tags'] = tags
                    yield config


def make_config(config):
    filename = re.sub('[^0-9a-zA-Z]+', '_', config['name'])
    with open(f'bambenekconsulting_{filename}.json', 'w') as f:
        json.dump(config, f, indent=2)


if __name__ == '__main__':
    c = Clusters()

    for entry in get_paths():
        make_config(entry)
