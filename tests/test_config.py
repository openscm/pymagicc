from os import environ

import pytest

from pymagicc.config import (ConfigStore, config, default_config,
                             lookup_defaults, lookup_env)


def temp_set_var(store):
    """
    Temporary sets a value of a Dict-like object for the duration of a test
    :param store: A Dict-like object which holds key-value pairs. The store is
        restored to its original state at the end of the test
    """
    prev_values = {}

    def set_var(name, value):
        if name not in prev_values:  # Only remember the first value
            prev_values[name] = store.get(name)
        if value is None:
            try:
                del store[name]
            except KeyError:
                pass
        else:
            store[name] = value

    def cleanup():
        # Clean up any set variables
        for n in prev_values:
            if prev_values[n] is not None:
                store[n] = prev_values[n]
            else:
                del store[n]

    return set_var, cleanup


@pytest.fixture(scope="function")
def env_override():
    set_var, cleanup = temp_set_var(environ)
    yield set_var
    cleanup()


@pytest.fixture(scope="function")
def config_override():
    set_var, cleanup = temp_set_var(config.overrides)
    yield set_var
    cleanup()


def test_lookup_default():
    assert lookup_defaults("EXECUTABLE_6") == default_config["EXECUTABLE_6"]
    assert lookup_defaults("execUTable_6") == default_config["EXECUTABLE_6"]
    assert lookup_defaults("SOMETHING") is None


def test_lookup_env(env_override):
    env_override("MAGICC_EXECUTABLE_6", "/foo/bar/magicc")
    assert lookup_env("EXECUTABLE_6") == "/foo/bar/magicc"
    assert lookup_env("executable_6") == "/foo/bar/magicc"

    assert lookup_env("OTHER") is None
    env_override("MAGICC_OTHER", "test")
    assert lookup_env("OTHER") == "test"

    # Something that isn't specified
    assert lookup_env("SOMETHING") is None


def test_simple_config():
    assert config["EXECUTABLE_6"] == default_config["EXECUTABLE_6"]


def test_precendence(env_override):
    c = ConfigStore()
    assert c["EXECUTABLE_6"] == default_config["EXECUTABLE_6"]

    env_override("MAGICC_EXECUTABLE_6", "/foo/bar/magicc")
    assert c["EXECUTABLE_6"] == "/foo/bar/magicc"

    c["executable_6"] = "testing"
    assert c["EXECUTABLE_6"] == "testing"


def test_overrides():
    c = ConfigStore()
    assert c["EXECUTABLE_6"] == default_config["EXECUTABLE_6"]

    c["executable_6"] = "testing"
    assert c["EXECUTABLE_6"] == "testing"
