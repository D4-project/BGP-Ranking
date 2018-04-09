#!/usr/bin/env python
# -*- coding: utf-8 -*-
from setuptools import setup


setup(
    name='bgpranking',
    version='0.1',
    author='Raphaël Vinot',
    author_email='raphael.vinot@circl.lu',
    maintainer='Raphaël Vinot',
    url='https://github.com/D4-project/BGP-Ranking',
    description='BGP Ranking, the new one..',
    packages=['bgpranking'],
    scripts=['bin/archiver.py', 'bin/dbinsert.py', 'bin/fetcher.py', 'bin/parser.py',
             'bin/loadprefixes.py', 'bin/rislookup.py', 'bin/sanitizer.py', 'bin/run_backend.py',
             'bin/monitor.py', 'bin/ranking.py', 'bin/start.py', 'bin/stop.py', 'bin/shutdown.py'],
    classifiers=[
        'License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)',
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Operating System :: POSIX :: Linux',
        'Intended Audience :: Science/Research',
        'Intended Audience :: Telecommunications Industry',
        'Intended Audience :: Information Technology',
        'Programming Language :: Python :: 3',
        'Topic :: Security',
        'Topic :: Internet',
    ],
    include_package_data=True,
    package_data={'config': ['config/*/*.conf',
                             'config/modules/*.json']},
)
