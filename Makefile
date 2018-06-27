all: venv

test: venv
	@[ ! -z "`which wine`" ] || echo 'If you want to test pymagicc fully on a non-windows system, install wine now'
	./venv/bin/pytest tests

venv: dev-requirements.txt
	[ -d ./venv ] || python3 -m venv venv
	./venv/bin/pip install --upgrade pip
	./venv/bin/pip install wheel
	./venv/bin/pip install -Ur dev-requirements.txt
	./venv/bin/jupyter serverextension enable --py --sys-prefix appmode
	./venv/bin/jupyter nbextension     enable --py --sys-prefix appmode
	./venv/bin/jupyter nbextension enable --py widgetsnbextension
	./venv/bin/pip install -e .
	touch venv

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
		--no-dependencies
	# Remove local directory from path to get actual installed version.
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
	$(TEMPVENV)/bin/pip install pymagicc
	$(TEMPVENV)/bin/python -c "import sys; sys.path.remove(''); import pymagicc; print(pymagicc.__version__)"

flake8: venv
	./venv/bin/flake8 pymagicc

docs/api.md: pymagicc/*.py
	pydocmd simple pymagicc+ pymagicc.api+ pymagicc.input++ pymagicc.config > docs/api.md

.PHONY: publish-on-testpypi test-testpypi-install publish-on-pypi test-pypi-install flake8 test
