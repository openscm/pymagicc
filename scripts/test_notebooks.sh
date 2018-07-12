#!/bin/bash

PYTEST=./venv/bin/pytest

if [ "$TRAVIS" = true ]; then
  PYTEST=pytest
fi

$PYTEST --nbval \
  notebooks/Example.ipynb \
  notebooks/Diagnose-TCR-ECS.ipynb \
--sanitize notebooks/tests_sanitize.cfg
