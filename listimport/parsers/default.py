#!/usr/bin/env python
# -*- coding: utf-8 -*-

from io import BytesIO
from datetime import datetime

from ..simple_feed_fetcher import RawFileImporter


class DefaultImporter(RawFileImporter):

    def parse_raw_file(self, f: BytesIO):
        self.datetime = datetime.now()
        return self.extract_ipv4(f.getvalue())
