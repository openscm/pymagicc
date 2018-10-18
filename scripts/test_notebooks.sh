#!/bin/bash

PYTEST=./venv/bin/pytest

if [ "$TRAVIS" = true ]; then
  PYTEST=pytest
fi

$PYTEST --nbval notebooks --sanitize notebooks/tests_sanitize.cfg
