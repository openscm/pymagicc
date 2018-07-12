#!/bin/bash
./venv/bin/pytest --nbval \
  notebooks/Example.ipynb \
  notebooks/Diagnose-TCR-ECS.ipynb \
--sanitize notebooks/tests_sanitize.cfg
