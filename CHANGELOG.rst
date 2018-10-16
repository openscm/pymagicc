Changelog
=========

master
------

- (`#139 <https://github.com/openclimatedata/pymagicc/pull/139>`_) Added the ability to read all MAGICC output files/throw an explanatory error with ``pymagicc.io.MAGICCData``
- (`#135 <https://github.com/openclimatedata/pymagicc/pull/135>`_) Moved emissions definitions to a single csv and packaged all of the definitions files using the `data package standard <https://frictionlessdata.io/docs/creating-tabular-data-packages-in-python/>`_
- (`#79 <https://github.com/openclimatedata/pymagicc/pull/79>`_) Confirmed that keeping track of config state works and added example to TCR/ECS diagnosis notebook
- (`#146 <https://github.com/openclimatedata/pymagicc/pull/146>`_) Removed path alteration from docs buiding
- (`#143 <https://github.com/openclimatedata/pymagicc/pull/143>`_) Only read ``PARAMETERS.OUT`` file if it exists. ``MAGICCBase.config`` now defaults to ``None`` until a valid ``PARAMETERS.OUT`` file is read.
- (`#133 <https://github.com/openclimatedata/pymagicc/pull/133>`_) Put definitions of MAGICC6's expected emissions into a standalone module
- (`#102 <https://github.com/openclimatedata/pymagicc/pull/102>`_) Added ability to read and write SCEN7 files
- (`#108 <https://github.com/openclimatedata/pymagicc/pull/108>`_) Added ability to read all files in MAGICC6 run folder (``pymagicc/MAGICC6/run``) to a common format
    - Note that this change means that only files which follow the MAGICC6 or MAGICC7 naming convention are supported. These are very similar to MAGICC5 except that emissions files must be named in the form ``*.SCEN``, ``*.SCEN7`` or ``*EMISX.IN`` where ``X`` is ``I`` if the file contains fossil and industrial emissions and ``B`` if the file contains agriculture, land-use and land-use change emissions. The suffixes ``FOSSIL&IND`` and ``LANDUSE`` are no longer supported.
    - The renamed files are
        - ``pymagicc/MAGICC6/run/EDGAR_NOX_EMIS_LANDUSE.IN`` => ``pymagicc/MAGICC6/run/EDGAR_NOXB_EMIS.IN``
        - ``pymagicc/MAGICC6/run/EDGAR_NOX_EMIS_FOSSIL&IND.IN`` => ``pymagicc/MAGICC6/run/EDGAR_NOXI_EMIS.IN``
        - ``pymagicc/MAGICC6/run/HOUGHTON_CO2_EMIS_LANDUSE.IN`` => ``pymagicc/MAGICC6/run/HOUGHTON_CO2B_EMIS.IN``
        - ``pymagicc/MAGICC6/run/MARLAND_CO2_EMIS_FOSSIL&IND.IN`` => ``pymagicc/MAGICC6/run/MARLAND_CO2I_EMIS.IN``
    - Deleted ``pymagicc/MAGICC6/run/HIST_SEALEVEL_CHURCHWHITE2006_RF.IN`` as it's empty
    - Added ``scripts/check_run_dir_file_read.py`` so we can quickly check which files in a MAGICC ``run`` directory can be read by ``pymagicc``
    - Added new section to docs, ``docs/file_conventions.rst`` which will document all of the relevant information related to MAGICC's file conventions

1.3.2
-----

- add short-term solution for reading Carbon Cycle output
- add clear error if a valid executable is not configured/found
- remove ``_magiccbinary`` variable
- partial steps towards updated input/output, still not fully tested
- add examples of file input/writing in notebook
- add expectexception so that we can show errors in notebooks with
  sensible CI

1.3.1
-----

- add TCR diagnosis function
- improve testing of notebooks
- add documentation using MkDocs
- use Black for automatic code formatting
- add Python 3.7 testing

1.2.0
-----

- drop support for Python 2
- rename RCP3PD to RCP26 and RCP6 to RCP60 for consistency and MAGICC7
  compatibility
- introduce new API functions for setting up and running MAGICC
- introduce ``config`` module
- remove ``output_dir`` from ``run`` function, this can be achieved using the new API
- change directory structure of the MAGICC version shipped with Pymagicc
  to be more similar to MAGICC7's structure
- add ``--skip-slow`` option to tests

1.1.0
-----

- add reading of MAGICC_EXECUTABLE environment variable to simplify
  setting path of MAGICC package for testing and CI
  (thanks ``@lewisjared``)

1.0.2
-----

- interactive demo Notebook using Jupyter Notebook's appmode
  extension
- documentation improvements

1.0.1
-----

- Un-pin f90nml dependency, 0.23 is working with Pymagicc again

1.0.0
-----

- API Stable release

0.9.3
-----

- workaround for bug in Pandas
  (`<https://github.com/pandas-dev/pandas/issues/18692>`_) when reading
  some files from alternative MAGICC builds
- improve documentation

0.9.2
-----

- add Windows testing and fix running on Windows
- simplify configuration by only having optional config parameters

0.8.0
-----

- pin f90nml version because later release breaks with MAGICC output

0.7.0
-----

- switch to Dictionaries as results object and scenarios data
  structure since Pandas panel is being deprecated.

0.6.4
-----

- returning used parameters in MAGICC ``run`` function is optional
- fix versioning for PyPI installs

0.4
---

Initial release.
