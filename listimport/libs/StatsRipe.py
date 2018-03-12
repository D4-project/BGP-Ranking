#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests


class StatsRIPE():

    def __init__(self, sourceapp='bgpranking-ng - CIRCL'):
        self.url = "https://stat.ripe.net/data/{method}/data.json?{parameters}"
        self.url_parameters = {'sourceapp': sourceapp}

    async def network_info(self, ip: str) -> dict:
        method = 'network-info'
        self.url_parameters['resource'] = ip
        parameters = '&'.join(['='.join(item) for item in self.url_parameters.items()])
        url = self.url.format(method=method, parameters=parameters)
        response = requests.get(url)
        return response.json()

    async def prefix_overview(self, prefix: str) -> dict:
        method = 'prefix-overview'
        self.url_parameters['resource'] = prefix
        parameters = '&'.join(['='.join(item) for item in self.url_parameters.items()])
        url = self.url.format(method=method, parameters=parameters)
        response = requests.get(url)
        return response.json()
