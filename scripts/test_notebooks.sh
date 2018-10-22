#!/bin/bash

PYTEST=./venv/bin/pytest

if [ "$TRAVIS" = true ]; then
  PYTEST=pytest
fi

# We don't want to test the Demo notebook as installing the widget is a pain
# We don't want to test the MAGICC7 notebook as the binary isn't available publicly
# and paths are a pain
$PYTEST --nbval $(find ./notebooks -name "*.ipynb" \( ! -name "*Demo*" -and ! -name "*MAGICC7*" \) -maxdepth 1) --sanitize notebooks/tests_sanitize.cfg
