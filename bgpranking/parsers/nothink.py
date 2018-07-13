#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from dateutil.parser import parse
import re
from io import BytesIO

from typing import List

def parse_raw_file(self, f: BytesIO)  -> List[bytes]:
    self.datetime = parse(re.findall(b'# Generated (.*)\n', f.getvalue())[0])
    return self.extract_ipv4(f.getvalue())
