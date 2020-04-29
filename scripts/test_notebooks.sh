#!/bin/bash

PYTEST=./venv/bin/pytest

if [ "$CI" = true ]; then
  PYTEST=pytest
fi

# We don't want to test the Demo notebook as installing the widget is a pain
# We don't want to test the MAGICC7 notebook as the binary isn't available publicly
$PYTEST \
    -r a  \
    --nbval \
    $(find ./notebooks -maxdepth 1 -name "*.ipynb" \( ! -name "*Demo*" -and ! -name "*MAGICC7*" \)) \
    --sanitize notebooks/tests_sanitize.cfg
