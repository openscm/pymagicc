from pymagicc.config import (
    ConfigStore,
    config,
    default_config,
    lookup_defaults,
    lookup_env,
)


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
