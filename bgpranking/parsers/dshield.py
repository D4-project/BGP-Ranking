#!/usr/bin/env python
# -*- coding: utf-8 -*-

from dateutil.parser import parse
import re
from io import BytesIO
from typing import List


def parse_raw_file(self, f: BytesIO) -> List[bytes]:
    self.datetime = parse(re.findall(b'# updated (.*)\n', f.getvalue())[0])
    iplist = self.extract_ipv4(f.getvalue())
    # The IPS have leading 0s. Getting tid of them directly here.
    return self.strip_leading_zeros(iplist)
