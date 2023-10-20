import datetime as dt
import os
import shutil
from os import environ
from os.path import exists
from tempfile import mkdtemp, mkstemp

import numpy as np
import pytest

from pymagicc import MAGICC6, MAGICC7
from pymagicc.config import _is_windows, _wine_installed, config
from pymagicc.io import MAGICCData


def pytest_addoption(parser):
    parser.addoption(
        "--skip-slow", action="store_true", default=False, help="skip any slow tests"
    )
    parser.addoption(
        "--update-expected-file",
        action="store_true",
        default=False,
        help="Overwrite expected files",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--skip-slow"):
        # --skip-slow given in cli: skipping slow tests
        skip_slow = pytest.mark.skip(reason="--skip-slow option was provided")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)


@pytest.fixture
def update_expected_file(request):
    return request.config.getoption("--update-expected-file")


def create_package(MAGICC_cls, **kwargs):
    p = MAGICC_cls(**kwargs)

    if p.executable is None or not exists(p.original_dir):
        magicc_x_unavailable = "MAGICC {} is not available.".format(p.version)
        env_text = (
            "Pymagicc related variables in your current environment are: {}.".format(
                ";".join(
                    [
                        "{}: {}".format(k, v)
                        for (k, v) in os.environ.items()
                        if k.startswith("MAGICC_")
                    ]
                )
            )
        )
        env_help = "If you set MAGICC_EXECUTABLE_X=/path/to/MAGICCX/binary then you will be able to run the tests with that binary for MAGICC_X."
        pytest.skip("\n".join([magicc_x_unavailable, env_text, env_help]))

    if p.version == 6 and (not _wine_installed) and (not _is_windows):
        pytest.xfail("Wine is not installed")

    p.create_copy()
    return p


@pytest.fixture(scope="function", params=[MAGICC6, MAGICC7])
def package(request):
    MAGICC_cls = request.param
    p = create_package(MAGICC_cls)
    yield p

    # Perform cleanup after tests are complete
    root_dir = p.root_dir
    p.remove_temp_copy()
    assert not exists(root_dir)


@pytest.fixture(scope="function", params=[MAGICC6, MAGICC7])
def package_non_strict(request):
    MAGICC_cls = request.param
    p = create_package(MAGICC_cls, strict=False)
    yield p

    # Perform cleanup after tests are complete
    root_dir = p.root_dir
    p.remove_temp_copy()
    assert not exists(root_dir)


@pytest.fixture
def temp_file():
    temp_file = mkstemp()[1]
    yield temp_file
    print("deleting {}".format(temp_file))
    os.remove(temp_file)


@pytest.fixture
def temp_dir():
    temp_dir = mkdtemp()
    yield temp_dir
    print("deleting {}".format(temp_dir))
    shutil.rmtree(temp_dir)


@pytest.fixture
def writing_base():
    no_cols = 4
    yield MAGICCData(
        np.arange(0, 2 * no_cols).reshape((2, no_cols)),
        index=np.arange(1995, 1997),
        columns={
            "region": ["region {}".format(i) for i in range(no_cols)],
            "scenario": ["test"],
            "model": ["unspecified"],
            "variable": ["variable"],
            "unit": ["unit"],
            "todo": ["SET"],
        },
    )


@pytest.fixture
def writing_base_emissions():
    no_cols = 5
    yield MAGICCData(
        np.arange(0, 2 * no_cols).reshape((2, no_cols)),
        index=np.arange(1995, 1997),
        columns={
            "region": ["region {}".format(i) for i in range(no_cols)],
            "scenario": ["test"],
            "model": ["unspecified"],
            "variable": ["variable"],
            "unit": ["unit"],
            "todo": ["SET"],
        },
    )


@pytest.fixture
def writing_base_mag():
    tregions = (
        ["World"]
        + ["World|{}".format(r) for r in ["Northern Hemisphere", "Southern Hemisphere"]]
        + ["World|{}".format(r) for r in ["Land", "Ocean"]]
    )

    writing_base_mag = MAGICCData(
        data=np.arange(27 * len(tregions)).reshape(27, len(tregions)),
        index=[
            dt.datetime(2099, 1, 16, 12, 0),
            dt.datetime(2099, 2, 15, 0, 0),
            dt.datetime(2099, 3, 16, 12, 0),
            dt.datetime(2099, 4, 16, 0, 0),
            dt.datetime(2099, 5, 16, 12, 0),
            dt.datetime(2099, 6, 16, 0, 0),
            dt.datetime(2099, 7, 16, 12, 0),
            dt.datetime(2099, 8, 16, 12, 0),
            dt.datetime(2099, 9, 16, 0, 0),
            dt.datetime(2099, 10, 16, 12, 0),
            dt.datetime(2099, 11, 16, 0, 0),
            dt.datetime(2099, 12, 16, 12, 0),
            dt.datetime(2100, 1, 16, 12, 0),
            dt.datetime(2100, 2, 15, 0, 0),
            dt.datetime(2100, 3, 16, 12, 0),
            dt.datetime(2100, 4, 16, 0, 0),
            dt.datetime(2100, 5, 16, 12, 0),
            dt.datetime(2100, 6, 16, 0, 0),
            dt.datetime(2100, 7, 16, 12, 0),
            dt.datetime(2100, 8, 16, 12, 0),
            dt.datetime(2100, 9, 16, 0, 0),
            dt.datetime(2100, 10, 16, 12, 0),
            dt.datetime(2100, 11, 16, 0, 0),
            dt.datetime(2100, 12, 16, 12, 0),
            dt.datetime(2101, 1, 16, 12, 0),
            dt.datetime(2101, 2, 15, 0, 0),
            dt.datetime(2101, 3, 16, 12, 0),
        ],
        columns={
            "region": tregions,
            "variable": "NPP",
            "model": "unspecified",
            "scenario": "mag test",
            "unit": "gC/yr",
            "todo": "SET",
        },
    )

    writing_base_mag.metadata = {
        "header": "Test mag file",
        "timeseriestype": "MONTHLY",
        "other info": "checking time point handling",
    }

    yield writing_base_mag


def temp_set_var(store):
    """
    Temporarily sets a value of a Dict-like object for the duration of a test
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
