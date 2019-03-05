import os
from os.path import exists, join, dirname
import pkg_resources
from tempfile import mkstemp, mkdtemp
from shutil import rmtree


import pytest
import numpy as np


from pymagicc import MAGICC6, MAGICC7
from pymagicc.io import MAGICCData


MAGICC6_DIR = pkg_resources.resource_filename("pymagicc", "MAGICC6/run")
TEST_DATA_DIR = join(dirname(__file__), "test_data")
TEST_OUT_DIR = join(TEST_DATA_DIR, "out_dir")

EXPECTED_FILES_DIR = join(TEST_DATA_DIR, "expected_files")


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


@pytest.fixture(scope="function", params=[MAGICC6, MAGICC7])
def package(request):
    MAGICC_cls = request.param
    p = MAGICC_cls()

    if p.executable is None or not exists(p.original_dir):
        magicc_x_unavailable = "MAGICC {} is not available.".format(p.version)
        env_text = "Pymagicc related variables in your current environment are: {}.".format(
            ";".join(
                [
                    "{}: {}".format(k, v)
                    for (k, v) in os.environ.items()
                    if k.startswith("MAGICC_")
                ]
            )
        )
        env_help = "If you set MAGICC_EXECUTABLE_X=/path/to/MAGICCX/binary then you will be able to run the tests with that binary for MAGICC_X."
        pytest.skip("\n".join([magicc_x_unavailable, env_text, env_help]))
    p.create_copy()
    root_dir = p.root_dir
    yield p
    # Perform cleanup after tests are complete
    p.remove_temp_copy()
    assert not exists(root_dir)


@pytest.fixture
def temp_file():
    temp_file = mkstemp()[1]
    yield temp_file
    print("deleting {}".format(temp_file))
    remove(temp_file)


@pytest.fixture
def temp_dir():
    temp_dir = mkdtemp()
    yield temp_dir
    print("deleting {}".format(temp_dir))
    rmtree(temp_dir)


@pytest.fixture
def writing_base():
    no_cols = 4
    yield MAGICCData(
        np.arange(0, 2 * no_cols).reshape((2, no_cols)),
        columns={
            "index": np.arange(1995, 1997),
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
        columns={
            "index": np.arange(1995, 1997),
            "region": ["region {}".format(i) for i in range(no_cols)],
            "scenario": ["test"],
            "model": ["unspecified"],
            "variable": ["variable"],
            "unit": ["unit"],
            "todo": ["SET"],
        },
    )
