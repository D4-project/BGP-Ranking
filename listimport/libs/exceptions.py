#!/usr/bin/env python
# -*- coding: utf-8 -*-


class BGPRankingException(Exception):
    pass


class FetcherException(BGPRankingException):
    pass


class ArchiveException(BGPRankingException):
    pass


class CreateDirectoryException(BGPRankingException):
    pass
