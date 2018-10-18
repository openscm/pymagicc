#!/bin/bash

PYTEST=./venv/bin/pytest

if [ "$TRAVIS" = true ]; then
  PYTEST=pytest
fi

# We don't want to test the Demo notebook as installing the widget is a pain
$PYTEST --nbval $(find ./notebooks -name "*.ipynb" ! -name "*Demo*" -maxdepth 1) --sanitize notebooks/tests_sanitize.cfg
