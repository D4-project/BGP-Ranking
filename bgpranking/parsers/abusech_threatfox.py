#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

from io import BytesIO
from typing import List


def parse_raw_file(self, f: BytesIO) -> List[str]:
    to_return = []
    for entry in json.loads(f.getvalue().decode()).values():
        ip_port = entry[0]['ioc_value']
        to_return.append(ip_port.split(':')[0])
    return to_return
