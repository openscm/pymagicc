"""
Module for collating configuration variables from various sources

The order of preference is:
Overrides > Environment variable > Defaults

Overrides can be set using the ConfigStore
"""

import platform
from os import environ
from os.path import abspath, dirname, join

__all__ = ["config"]

_is_windows = platform.system() == "Windows"
# Default configuration parameters for pymagicc
default_config = {
    "EXECUTABLE_6": join(dirname(abspath(__file__)), "MAGICC6/run/magicc6.exe"),
    "IS_WINDOWS": _is_windows,
}


def lookup_defaults(item):
    return default_config.get(item.upper())


def lookup_env(item):
    env_var = "MAGICC_" + item.upper()
    return environ.get(env_var)


class ConfigStore(object):
    """
    A list of functions which, given an item, attempts to find the associated
    config variable. All queries are case insensitive. If a lookup cannot
    find the item return None
    This list is in decending order of priority
    """

    def __init__(self):
        self.overrides = {}

        self.config_lookups = [lookup_env, lookup_defaults]

    def __getitem__(self, item):
        item = item.upper()
        if item in self.overrides:
            return self.overrides[item]

        for lookup in self.config_lookups:
            c = lookup(item)
            if c is not None:
                return c

    def __setitem__(self, key, value):
        self.overrides[key.upper()] = value


config = ConfigStore()
