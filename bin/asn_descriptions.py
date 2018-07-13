#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from pathlib import Path

from bgpranking.abstractmanager import AbstractManager
from bgpranking.asn_descriptions import ASNDescriptions
from bgpranking.libs.helpers import get_homedir

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO, datefmt='%I:%M:%S')


class ASNDescriptionsManager(AbstractManager):

    def __init__(self, storage_directory: Path=None, loglevel: int=logging.DEBUG):
        super().__init__(loglevel)
        if not storage_directory:
            storage_directory = get_homedir() / 'rawdata'
        self.asn_descr = ASNDescriptions(storage_directory, loglevel)

    def _to_run_forever(self):
        self.asn_descr.load_descriptions()


if __name__ == '__main__':
    asnd_manager = ASNDescriptionsManager()
    asnd_manager.run(sleep_in_sec=3600)
