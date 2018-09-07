Master
=====

- (#108)[https://github.com/openclimatedata/pymagicc/pull/108] Added ability to read all files in MAGICC6 run folder (`pymagicc/MAGICC6/run`) to a common format


1.3.2
=====

- add short-term solution for reading Carbon Cycle output
- add clear error if a valid executable is not configured/found
- remove `_magiccbinary` variable
- partial steps towards updated input/output, still not fully tested
- add examples of file input/writing in notebook
- add expectexception so that we can show errors in notebooks with
  sensible CI

1.3.1
=====

- add TCR diagnosis function
- improve testing of notebooks
- add documentation using MkDocs
- use Black for automatic code formatting
- add Python 3.7 testing

1.2.0
=====

- drop support for Python 2
- rename RCP3PD to RCP26 and RCP6 to RCP60 for consistency and MAGICC7
  compatibility
- introduce new API functions for setting up and running MAGICC
- introduce `config` module
- remove `output_dir` from `run` function, this can be achieved using the new API
- change directory structure of the MAGICC version shipped with Pymagicc
  to be more similar to MAGICC7's structure
- add \--skip-slow option to tests

1.1.0
=====

- add reading of MAGICC\_EXECUTABLE environment variable to simplify
  setting path of MAGICC package for testing and CI
  (thanks @lewisjared)

1.0.2
=====

- interactive demo Notebook using Jupyter Notebook\'s appmode
  extension
- documentation improvements

1.0.1
=====

- Un-pin f90nml dependency, 0.23 is working with Pymagicc again

1.0.0
=====

- API Stable release

0.9.3
=====

- workaround for bug in Pandas
  (<https://github.com/pandas-dev/pandas/issues/18692>) when reading
  some files from alternative MAGICC builds
- improve documentation

0.9.2
=====

- add Windows testing and fix running on Windows
- simplify configuration by only having optional config parameters

0.8.0
=====

- pin f90nml version because later release breaks with MAGICC output

0.7.0
=====

- switch to Dictionaries as results object and scenarios data
  structure since Pandas panel is being deprecated.

0.6.4
=====

- returning used parameters in MAGICC `run` function is optional
- fix versioning for PyPI installs

0.4
===

Initial release.
