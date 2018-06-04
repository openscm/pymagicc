"""
Module for collating configuration variables from various sources

The order of preference is:
Environment variable > User configuration file > Defaults
"""

import platform
from os import environ
from os.path import abspath, dirname, exists, expanduser, join

import yaml

__all__ = ['config']

_is_windows = platform.system() == "Windows"
# Default configuration parameters for pymagicc
default_config = {
    'EXECUTABLE': join(dirname(abspath(__file__)),
                       "MAGICC6/run/magicc6.exe"
                       ),
    'WINDOWS': _is_windows
}

_xdg_home = environ.get('XDG_CONFIG_HOME', expanduser('~/.config/'))


def user_config_file():
    """
    Get the file name for the user-level config file.

    This configuration file is stored in the User profile and contains any user
    specific overrides to pymagicc configuration. Under Windows this file will
    be named `%USERPROFILE%/.pymagicc.yml` for other OS the file should be
    located at `~/.config/pymagicc.yml`. This file is not created by default
    """
    if _is_windows:
        return expanduser('~\\.pymagicc.yml')
    return join(_xdg_home, 'pymagicc.yml')


def parse_config_file(fname):
    """
    Read in a configuration file from a given filename
    :param fname:
    :return: The configuration in the file as a Dict, else None if the file
        could not be found
    """
    if exists(fname):
        data = yaml.load(open(fname))
        # Convert all keys to uppercase
        return {k.upper(): v for k, v in data.items()}


def lookup_defaults(item):
    return default_config.get(item.upper())


def lookup_env(item):
    env_var = 'MAGICC_' + item.upper()
    return environ.get(env_var)


def lookup_file(fname):
    """
    Lookup a yaml configuration file
    :param fname: The filename to query
    :return: The function to perform the lookup. Takes a item name and returns
        the configuration value if it is present or None
    """
    data = parse_config_file(fname)

    def perform_lookup(item):
        # No file was found
        if data is None:
            return None
        return data.get(item.upper())

    return perform_lookup


class ConfigStore(object):
    """
    A list of functions which given, a item attempts to find the associated
    config variable. All queries are case insensitive. If a lookup cannot
    find the item return None
    This list is in decending order of priority
    """
    config_lookups = [
        lookup_env,
        lookup_file(user_config_file()),
        lookup_defaults
    ]

    def __getitem__(self, item):
        for lookup in self.config_lookups:
            c = lookup(item)
            if c is not None:
                return c


config = ConfigStore()
