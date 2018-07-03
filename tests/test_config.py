from os import environ

import pytest
from pymagicc.config import config, ConfigStore, default_config, \
    lookup_defaults, lookup_env


@pytest.fixture(scope="function")
def env_var():
    # Set environment variables for the duration of the test
    prev_values = {}

    def set_env_var(name, value):
        prev_values[name] = environ.get(name)
        environ[name] = value

    yield set_env_var

    # Clean up any set env variables
    for n in prev_values:
        if prev_values[n] is not None:
            environ[n] = prev_values[n]
        else:
            del environ[n]


def test_lookup_default():
    assert lookup_defaults('EXECUTABLE_6') == default_config['EXECUTABLE_6']
    assert lookup_defaults('execUTable_6') == default_config['EXECUTABLE_6']
    assert lookup_defaults('SOMETHING') is None


def test_lookup_env(env_var):
    env_var('MAGICC_EXECUTABLE_6', '/foo/bar/magicc')
    assert lookup_env('EXECUTABLE_6') == '/foo/bar/magicc'
    assert lookup_env('executable_6') == '/foo/bar/magicc'

    assert lookup_env('OTHER') is None
    env_var('MAGICC_OTHER', 'test')
    assert lookup_env('OTHER') == 'test'

    # Something that isn't specified
    assert lookup_env('SOMETHING') is None


def test_simple_config():
    assert config['EXECUTABLE_6'] == default_config['EXECUTABLE_6']


def test_precendence(env_var):
    c = ConfigStore()
    assert c['EXECUTABLE_6'] == default_config['EXECUTABLE_6']

    env_var('MAGICC_EXECUTABLE_6', '/foo/bar/magicc')
    assert c['EXECUTABLE_6'] == '/foo/bar/magicc'

    c['executable_6'] = 'testing'
    assert c['EXECUTABLE_6'] == 'testing'


def test_overrides():
    c = ConfigStore()
    assert c['EXECUTABLE_6'] == default_config['EXECUTABLE_6']

    c['executable_6'] = 'testing'
    assert c['EXECUTABLE_6'] == 'testing'
