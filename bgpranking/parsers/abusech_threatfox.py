#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json

from datetime import datetime
from io import BytesIO
from typing import List


def parse_raw_file(self, f: BytesIO) -> List[str]:
    self.datetime = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    to_return = []
    for entry in json.loads(f.getvalue().decode()).values():
        ip_port = entry[0]['ioc_value']
        to_return.append(ip_port.split(':')[0])
    return to_return
