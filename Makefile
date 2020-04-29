.DEFAULT_GOAL := help

VENV_DIR ?= venv
TESTS_DIR=$(PWD)/tests

define PRINT_HELP_PYSCRIPT
import re, sys

for line in sys.stdin:
	match = re.match(r'^([a-zA-Z_-]+):.*?## (.*)$$', line)
	if match:
		target, help = match.groups()
		print("%-20s %s" % (target, help))
endef
export PRINT_HELP_PYSCRIPT

.PHONY: help
help:
	@python -c "$$PRINT_HELP_PYSCRIPT" < $(MAKEFILE_LIST)

all: $(VENV_DIR)

checks: $(VENV_DIR)  ## run all the checks
	@echo "=== bandit ==="; $(VENV_DIR)/bin/bandit -c .bandit.yml -r pymagicc || echo "--- bandit failed ---" >&2; \
		echo "\n\n=== black ==="; $(VENV_DIR)/bin/black --check pymagicc tests setup.py docs/conf.py --exclude pymagicc/_version.py || echo "--- black failed ---" >&2; \
		echo "\n\n=== flake8 ==="; $(VENV_DIR)/bin/flake8 pymagicc tests setup.py || echo "--- flake8 failed ---" >&2; \
		echo "\n\n=== isort ==="; $(VENV_DIR)/bin/isort --check-only --quiet --recursive pymagicc tests setup.py || echo "--- isort failed ---" >&2; \
		echo "\n\n=== pydocstyle ==="; $(VENV_DIR)/bin/pydocstyle pymagicc || echo "--- pydocstyle failed ---" >&2; \
		echo "\n\n=== pylint ==="; $(VENV_DIR)/bin/pylint pymagicc || echo "--- pylint failed ---" >&2; \
		echo "\n\n=== notebook tests ==="; $(VENV_DIR)/bin/pytest notebooks -r a --nbval --sanitize-with tests/notebook-tests.cfg || echo "--- notebook tests failed ---" >&2; \
		echo "\n\n=== tests ==="; $(VENV_DIR)/bin/pytest tests --cov -rfsxEX --cov-report term-missing || echo "--- tests failed ---" >&2; \
		echo "\n\n=== docs ==="; $(VENV_DIR)/bin/sphinx-build -M html docs/source docs/build -qW || echo "--- docs failed ---" >&2; \
		echo

test: $(VENV_DIR)  ## run the tests
	@[ ! -z "`which wine`" ] || echo 'If you want to test pymagicc fully on a non-windows system, install wine now'
	$(VENV_DIR)/bin/pytest -r a tests --durations=10

test-notebooks: $(VENV_DIR) notebooks/*.ipynb scripts/test_notebooks.sh  ## run the notebook tests
	./scripts/test_notebooks.sh

$(VENV_DIR): setup.py
	[ -d $(VENV_DIR) ] || python3 -m venv $(VENV_DIR)

	$(VENV_DIR)/bin/pip install --upgrade pip
	$(VENV_DIR)/bin/pip install -e .[dev]

	$(VENV_DIR)/bin/jupyter serverextension enable --py --sys-prefix appmode
	$(VENV_DIR)/bin/jupyter nbextension     enable --py --sys-prefix appmode
	$(VENV_DIR)/bin/jupyter nbextension enable --py widgetsnbextension

	touch $(VENV_DIR)

update-example-plot:  ## update the example plot
	$(VENV_DIR)/bin/python scripts/plot_example.py

# first time setup, follow the 'Register for PyPI' section in this
# https://blog.jetbrains.com/pycharm/2017/05/how-to-publish-your-package-on-pypi/
# then this works
publish-on-testpypi: $(VENV_DIR)  ## release this version on test PyPI
	-rm -rf build dist
	@status=$$(git status --porcelain); \
	if test "x$${status}" = x; then \
		$(VENV_DIR)/bin/python setup.py bdist_wheel --universal; \
		$(VENV_DIR)/bin/twine upload -r testpypi dist/*; \
	else \
		echo Working directory is dirty >&2; \
	fi;

test-testpypi-install: $(VENV_DIR)  ## test installation from test PyPI
	$(eval TEMPVENV := $(shell mktemp -d))
	python3 -m venv $(TEMPVENV)
	$(TEMPVENV)/bin/pip install pip --upgrade
	# Install dependencies not on testpypi registry
	$(TEMPVENV)/bin/pip install pandas f90nml
	# Install pymagicc without dependencies.
	$(TEMPVENV)/bin/pip install \
		-i https://testpypi.python.org/pypi pymagicc \
		--no-dependencies --pre
	# Remove local directory from path to get actual installed version.
	@echo "This doesn't test dependencies"
	$(TEMPVENV)/bin/python -c "import sys; sys.path.remove(''); import pymagicc; print(pymagicc.__version__)"

publish-on-pypi: $(VENV_DIR)  ## release this version on PyPI
	-rm -rf build dist
	@status=$$(git status --porcelain); \
	if test "x$${status}" = x; then \
		$(VENV_DIR)/bin/python setup.py sdist bdist_wheel --universal; \
		$(VENV_DIR)/bin/twine upload dist/*; \
	else \
		echo Working directory is dirty >&2; \
	fi;

test-pypi-install: $(VENV_DIR)  ## test installation from PyPI
	$(eval TEMPVENV := $(shell mktemp -d))
	python3 -m venv $(TEMPVENV)
	$(TEMPVENV)/bin/pip install pip --upgrade
	$(TEMPVENV)/bin/pip install pymagicc --pre
	$(TEMPVENV)/bin/python scripts/test_install.py

docs: $(VENV_DIR) docs/*.rst $(shell find ./pymagicc/ -type f -name '*.py')  ## make the docs
	$(VENV_DIR)/bin/sphinx-build -M html docs docs/build

flake8: $(VENV_DIR)  ## apply the flake8 linter
	$(VENV_DIR)/bin/flake8 pymagicc

black: $(VENV_DIR)  ## reformat the code with black
	@status=$$(git status --porcelain pymagicc tests); \
	if test "x$${status}" = x; then \
		$(VENV_DIR)/bin/black --exclude _version.py setup.py pymagicc tests; \
	else \
		echo Not trying any formatting. Working directory is dirty ... >&2; \
	fi;

validate-data: $(VENV_DIR)  ## validate the data packaged in pymagicc
	$(VENV_DIR)/bin/goodtables pymagicc/definitions/datapackage.json

clean:  ## remove the virtual environment
	rm -rf $(VENV_DIR)

.PHONY: publish-on-testpypi test-testpypi-install publish-on-pypi test-pypi-install flake8 test black clean
