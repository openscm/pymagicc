"""
Module for collating configuration variables from various sources

The order of preference is:
Overrides > Environment variable > Defaults

Overrides can be set using the :class:`ConfigStore`
"""

import platform
import subprocess  # nosec # have to use subprocess
from os import environ
from os.path import abspath, dirname, join

__all__ = ["config"]

_is_windows = platform.system() == "Windows"
# Default configuration parameters for pymagicc
default_config = {
    "EXECUTABLE_6": join(dirname(abspath(__file__)), "MAGICC6/run/magicc6.exe"),
    "IS_WINDOWS": _is_windows,
}
_wine_installed = (
    subprocess.call(  # nosec # require subprocess call here
        "type wine", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    == 0
)


def lookup_defaults(item):
    """
    Retrive configuration from ``pymagicc.config.default_config``

    Parameters
    ----------
    item : str
        Configuration to lookup (case insensitive)

    Returns
    -------
    str
        Configuration
    """
    return default_config.get(item.upper())


def lookup_env(item):
    """
    Retrive configuration from environment

    We look for an environment variable named ``MAGICC_[item]``, where
    ``[item]`` is replaced by the value of ``item.upper()``.

    Parameters
    ----------
    item : str
        Configuration to lookup

    Returns
    -------
    str
        Configuration
    """
    env_var = "MAGICC_" + item.upper()
    return environ.get(env_var)


class ConfigStore:
    """
    Class which, given an item, attempts to find the associated config variable.

    All queries are case insensitive. If a lookup cannot find the item,
    ``None`` is returned. The items are looked up in the following order:

        #. user overrides (stored in ``.overrides``)
        #. environment variables
        #. defaults

    """

    def __init__(self):
        """
        Initialise
        """
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
