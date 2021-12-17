#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import logging
from dateutil.parser import parse
from datetime import timedelta

from bgpranking.helpers import load_all_modules_configs
from .ranking import Ranking

logging.basicConfig(format='%(asctime)s %(name)s %(levelname)s:%(message)s',
                    level=logging.INFO)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Manually force the ranking of a day or a time interval.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-d', '--day', type=str, help='Day to rank (Format: YYYY-MM-DD).')
    group.add_argument('-i', '--interval', type=str, nargs=2, help='Interval to rank, first to last (Format: YYYY-MM-DD YYYY-MM-DD).')
    args = parser.parse_args()

    ranking = Ranking(loglevel=logging.DEBUG)
    config_files = load_all_modules_configs()
    if args.day:
        day = parse(args.day).date().isoformat()
        ranking.rank_a_day(day)
    else:
        current = parse(args.interval[1]).date()
        stop_date = parse(args.interval[0]).date()
        while current >= stop_date:
            ranking.rank_a_day(current.isoformat())
            current -= timedelta(days=1)
