#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from dateutil.parser import parse
from csv import DictReader
from io import BytesIO, StringIO
from typing import Tuple, Generator
from datetime import datetime


def parse_raw_file(self, f: BytesIO) -> Generator[Tuple[str, datetime], None, None]:
    default_ts = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    reader = DictReader(StringIO(f.getvalue().decode()))
    for row in reader:
        if 'timestamp' in row:
            ts = parse(row['timestamp'])
        else:
            ts = default_ts

        if 'ip' in row:
            ip = row['ip']
        elif 'src_ip' in row:
            # For sinkhole6_http
            ip = row['src_ip']
        else:
            self.logger.critical(f'No IPs in the list {self.source}.')
            break
        yield ip, ts
