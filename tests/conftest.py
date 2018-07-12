import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--skip-slow", action="store_true", default=False, help="skip any slow tests"
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--skip-slow"):
        # --skip-slow given in cli: skipping slow tests
        skip_slow = pytest.mark.skip(reason="--skip-slow option was provided")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
