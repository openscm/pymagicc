all: venv

test: venv
	@[ ! -z "`which wine`" ] || echo 'If you want to test pymagicc fully on a non-windows system, install wine now'
	./venv/bin/pytest -rfsxEX tests

test-notebooks: venv notebooks/*.ipynb
	./scripts/test_notebooks.sh

venv: setup.py
	[ -d ./venv ] || python3 -m venv venv
	./venv/bin/pip install --upgrade pip
	./venv/bin/pip install -e .[tests,docs,deploy,dev]
	./venv/bin/jupyter serverextension enable --py --sys-prefix appmode
	./venv/bin/jupyter nbextension     enable --py --sys-prefix appmode
	./venv/bin/jupyter nbextension enable --py widgetsnbextension
	touch venv

update-example-plot:
	./venv/bin/python scripts/plot_example.py

# first time setup, follow the 'Register for PyPI' section in this
# https://blog.jetbrains.com/pycharm/2017/05/how-to-publish-your-package-on-pypi/
# then this works
publish-on-testpypi: venv
	-rm -rf build dist
	@status=$$(git status --porcelain); \
	if test "x$${status}" = x; then \
		./venv/bin/python setup.py bdist_wheel --universal; \
		./venv/bin/twine upload -r testpypi dist/*; \
	else \
		echo Working directory is dirty >&2; \
	fi;

test-testpypi-install: venv
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

publish-on-pypi: venv
	-rm -rf build dist
	@status=$$(git status --porcelain); \
	if test "x$${status}" = x; then \
		./venv/bin/python setup.py bdist_wheel --universal; \
		./venv/bin/twine upload dist/*; \
	else \
		echo Working directory is dirty >&2; \
	fi;

test-pypi-install: venv
	$(eval TEMPVENV := $(shell mktemp -d))
	python3 -m venv $(TEMPVENV)
	$(TEMPVENV)/bin/pip install pip --upgrade
	$(TEMPVENV)/bin/pip install pymagicc --pre
	$(TEMPVENV)/bin/python scripts/test_install.py

docs: docs/*.rst $(shell find ./pymagicc/ -type f -name '*.py') venv
	./venv/bin/sphinx-build -M html docs docs/build

flake8: venv
	./venv/bin/flake8 pymagicc

black: venv
	@status=$$(git status --porcelain pymagicc tests); \
	if test "x$${status}" = x; then \
		./venv/bin/black --exclude _version.py setup.py pymagicc tests; \
	else \
		echo Not trying any formatting. Working directory is dirty ... >&2; \
	fi;

validate-data: venv
	./venv/bin/goodtables pymagicc/definitions/datapackage.json

clean:
	rm -rf venv

.PHONY: publish-on-testpypi test-testpypi-install publish-on-pypi test-pypi-install flake8 test black clean
