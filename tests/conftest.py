import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--no-slow", action="store_true", default=False,
        help="skip any slow tests"
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--no-slow"):
        # --noslow given in cli: skip slow tests
        skip_slow = pytest.mark.skip(reason="need --noslow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
