venv: dev-requirements.txt
	[ -d ./venv ] || python3 -m venv venv
	./venv/bin/pip install --upgrade pip
	./venv/bin/pip install -Ur dev-requirements.txt

publish-on-testpypi:
	python setup.py register -r https://testpypi.python.org/pypi
	python setup.py sdist upload -r https://testpypi.python.org/pypi

test-testpypi-install:
	$(eval TEMPVENV := $(shell mktemp -d))
	python3 -m venv $(TEMPVENV)
	$(TEMPVENV)/bin/pip install pip --upgrade
	$(TEMPVENV)/bin/pip install pandas f90nml
	$(TEMPVENV)/bin/pip install \
		-i https://testpypi.python.org/pypi pymagicc \
		--no-dependencies
	$(TEMPVENV)/bin/python -c "import sys; sys.path.remove(''); import pymagicc; print(pymagicc.__version__)"

publish-on-pypi:
	python setup.py register -r https://pypi.python.org/pypi
	python setup.py sdist upload -r https://pypi.python.org/pypi

test-pypi-install:
	$(eval TEMPVENV := $(shell mktemp -d))
	python3 -m venv $(TEMPVENV)
	$(TEMPVENV)/bin/pip install pip --upgrade
	$(TEMPVENV)/bin/pip install pymagicc
	$(TEMPVENV)/bin/python -c "import sys; sys.path.remove(''); import pymagicc; print(pymagicc.__version__)"


.PHONY: publish-on-testpypi test-testpypi-install publish-on-pypi test-pypi-install
