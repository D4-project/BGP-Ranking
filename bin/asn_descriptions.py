#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import re
import requests

from dateutil.parser import parse
from redis import Redis

from bgpranking.default import get_socket_path, safe_create_dir, AbstractManager, get_config
from bgpranking.helpers import get_data_dir

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO)


class ASNDescriptions(AbstractManager):

    def __init__(self, loglevel: int=logging.INFO):
        super().__init__(loglevel)
        self.script_name = 'asn_descr'
        self.asn_meta = Redis(get_config('generic', 'storage_db_hostname'), get_config('generic', 'storage_db_port'), db=2, decode_responses=True)
        self.logger.debug('Starting ASN History')
        self.directory = get_data_dir() / 'asn_descriptions'
        safe_create_dir(self.directory)
        self.archives = self.directory / 'archive'
        safe_create_dir(self.archives)
        self.url = 'https://www.cidr-report.org/as2.0/autnums.html'

    def __update_available(self):
        r = requests.head(self.url)
        print(r.headers)
        current_last_modified = parse(r.headers['Last-Modified'])
        if not self.asn_meta.exists('ans_description_last_update'):
            return True
        last_update = parse(self.asn_meta.get('ans_description_last_update'))  # type: ignore
        if last_update < current_last_modified:
            return True
        return False

    def load_descriptions(self):
        if not self.__update_available():
            self.logger.debug('No new file to import.')
            return
        self.logger.info('Importing new ASN descriptions.')
        r = requests.get(self.url)
        last_modified = parse(r.headers['Last-Modified']).isoformat()
        p = self.asn_meta.pipeline()
        new_asn = 0
        new_description = 0
        for asn, descr in re.findall('as=AS(.*)&.*</a> (.*)\n', r.text):
            existing_descriptions = self.asn_meta.hgetall(f'{asn}|descriptions')
            if not existing_descriptions:
                self.logger.debug(f'New ASN: {asn} - {descr}')
                p.hset(f'{asn}|descriptions', last_modified, descr)
                new_asn += 1
            else:
                last_descr = sorted(existing_descriptions.keys(), reverse=True)[0]
                if descr != existing_descriptions[last_descr]:
                    self.logger.debug(f'New description for {asn}: {existing_descriptions[last_descr]} -> {descr}')
                    p.hset(f'{asn}|descriptions', last_modified, descr)
                    new_description += 1
        p.set('ans_description_last_update', last_modified)
        p.execute()
        self.logger.info(f'Done with import. New ASNs: {new_asn}, new descriptions: {new_description}')
        if new_asn or new_description:
            with open(self.archives / f'{last_modified}.html', 'w') as f:
                f.write(r.text)

    def _to_run_forever(self):
        self.load_descriptions()


def main():
    asnd_manager = ASNDescriptions()
    asnd_manager.run(sleep_in_sec=3600)


if __name__ == '__main__':
    main()
