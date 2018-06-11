#!/usr/bin/env python
# -*- coding: utf-8 -*-

from dateutil.parser import parse
import re
from io import BytesIO


def parse_raw_file(self, f: BytesIO):
    self.datetime = parse(re.findall(b'## Feed generated at: (.*)\n', f.getvalue())[0])
    return self.extract_ipv4(f.getvalue())
