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


class MissingEnv(BGPRankingException):
    pass


class InvalidDateFormat(BGPRankingException):
    pass


class MissingConfigFile(BGPRankingException):
    pass


class MissingConfigEntry(BGPRankingException):
    pass


class ThirdPartyUnreachable(BGPRankingException):
    pass
