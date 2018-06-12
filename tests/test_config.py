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
    assert lookup_defaults('EXECUTABLE') == default_config['EXECUTABLE']
    assert lookup_defaults('execUTable') == default_config['EXECUTABLE']
    assert lookup_defaults('SOMETHING') is None


def test_lookup_env(env_var):
    env_var('MAGICC_EXECUTABLE', '/foo/bar/magicc')
    assert lookup_env('EXECUTABLE') == '/foo/bar/magicc'
    assert lookup_env('executable') == '/foo/bar/magicc'

    assert lookup_env('OTHER') is None
    env_var('MAGICC_OTHER', 'test')
    assert lookup_env('OTHER') == 'test'

    # Something that isn't specified
    assert lookup_env('SOMETHING') is None


def test_simple_config():
    assert config['EXECUTABLE'] == default_config['EXECUTABLE']


def test_precendence(env_var):
    c = ConfigStore()
    assert c['EXECUTABLE'] == default_config['EXECUTABLE']

    env_var('MAGICC_EXECUTABLE', '/foo/bar/magicc')
    assert c['EXECUTABLE'] == '/foo/bar/magicc'

    c['executable'] = 'testing'
    assert c['EXECUTABLE'] == 'testing'


def test_overrides():
    c = ConfigStore()
    assert c['EXECUTABLE'] == default_config['EXECUTABLE']

    c['executable'] = 'testing'
    assert c['EXECUTABLE'] == 'testing'
