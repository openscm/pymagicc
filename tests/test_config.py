from os import environ

import pytest
from mock import patch
from pymagicc.config import config, lookup_defaults, lookup_env, lookup_file


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
    assert lookup_defaults('EXECUTABLE') == 'MAGICC6/magicc6.exe'
    assert lookup_defaults('execUTable') == 'MAGICC6/magicc6.exe'
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


@patch('pymagicc.config.parse_config_file')
def test_lookup_file(mock_config):
    mock_config.return_value = {
        'EXECUTABLE': '/foo/bar/magicc'
    }
    looker = lookup_file('/foo/test.yml')

    assert looker('EXECUTABLE') == '/foo/bar/magicc'
    assert looker('executable') == '/foo/bar/magicc'

    # Check the the file was only loaded once no matter how many function calls
    mock_config.assert_called_once()
    mock_config.assert_called_with('/foo/test.yml')


@patch('pymagicc.config.exists')
def test_lookup_file_missing(mock_exists):
    mock_exists.return_value = False

    looker = lookup_file('/foo/test.yml')

    assert looker('EXECUTABLE') is None

    mock_exists.assert_called_with('/foo/test.yml')


def test_simple_config():
    assert config['EXECUTABLE'] == 'MAGICC6/magicc6.exe'


@patch('pymagicc.config.parse_config_file')
def test_precendence(mock_config, env_var):
    # replace the default lookup with a mocked one
    mock_config.return_value = None
    config.config_lookups[1] = lookup_file('/foo/test.yml')

    assert config['EXECUTABLE'] == 'MAGICC6/magicc6.exe'

    # replace the default lookup with a mocked one
    mock_config.return_value = {
        'EXECUTABLE': '/foo/file/magicc'
    }
    config.config_lookups[1] = lookup_file('/foo/test.yml')
    assert config['EXECUTABLE'] == '/foo/file/magicc'

    env_var('MAGICC_EXECUTABLE', '/foo/bar/magicc')
    assert config['EXECUTABLE'] == '/foo/bar/magicc'
