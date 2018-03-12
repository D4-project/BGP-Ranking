#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
from pathlib import Path
from .exceptions import CreateDirectoryException


def safe_create_dir(to_create: Path):
    if to_create.exists() and not to_create.is_dir():
        raise CreateDirectoryException('The path {} already exists and is not a directory'.format(to_create))
    os.makedirs(to_create, exist_ok=True)
