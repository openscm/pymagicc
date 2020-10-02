Changelog
=========

master
------

- (`#311 <https://github.com/openscm/pymagicc/pull/311>`_) Fix naming of ocean heat content and ocean heat uptake output variables to match RCMIP conventions
- (`#310 <https://github.com/openscm/pymagicc/pull/310>`_) Rename ``pymagicc.io.prn`` to ``pymagicc.io.prn_files`` as PRN is a reserved filename on Windows
- (`#307 <https://github.com/openscm/pymagicc/pull/307>`_) Use ``scmdata.ScmRun`` as a base class for ``MAGICCData`` instead of the deprecated ``scmdata.ScmDataFrame`` (closes `#295 <https://github.com/openscm/pymagicc/issues/295>`_)
- (`#305 <https://github.com/openscm/pymagicc/pull/305>`_) Added functionality to read new MAGICC binary format which includes units
- (`#306 <https://github.com/openscm/pymagicc/pull/306>`_) Copy ``run`` folder recursively when creating temporary copy
- (`#238 <https://github.com/openscm/pymagicc/pull/238>`_) Add documentation for handling of World region in ``.SCEN7`` files
- (`#303 <https://github.com/openscm/pymagicc/pull/303>`_) Refactor ``pymagicc.io`` into multiple files
- (`#301 <https://github.com/openscm/pymagicc/pull/301>`_) Add MAGICC7 variables ``AEROSOL_RF``, ``HEAT_EARTH`` and ``HEAT_NONOCEAN``
- (`#299 <https://github.com/openscm/pymagicc/pull/299>`_) Make conversion of FORTRAN safe units apply to ``.MAG`` files too and be more consistent
- (`#300 <https://github.com/openscm/pymagicc/pull/300>`_) Fix name in docs (closes `#205 <https://github.com/openscm/pymagicc/issues/205>`_)
- (`#298 <https://github.com/openscm/pymagicc/pull/298>`_) Make SCEN7 writing work with single variables
- (`#297 <https://github.com/openscm/pymagicc/pull/297>`_) Make Binary reader able to handle global-only binary output
- (`#293 <https://github.com/openscm/pymagicc/pull/293>`_) Update CI to use GitHub actions
- (`#294 <https://github.com/openscm/pymagicc/pull/294>`_) Convert the direct aerosols variable names from MAGICC in a consistent way. Renamed ``definitions/magicc_emisssions_units.csv`` to ``definitions/magicc_emissions_units.csv``
- (`#291 <https://github.com/openscm/pymagicc/pull/291>`_) Switch to using the ``_ERF`` suffix for IPCC definition of Effective Radiative Forcing variables. This replaces ``_EFFRF`` which is a MAGICC internal variable and was incorrectly labelled as Effective Radiative Forcing.
- (`#277 <https://github.com/openscm/pymagicc/pull/277>`_) Add MAGICC7 compact output file readers
- (`#281 <https://github.com/openscm/pymagicc/pull/281>`_) Hotfix readers and writers for ``.DAT`` files (``thisfile_datacolumns`` was wrong)
- (`#288 <https://github.com/openscm/pymagicc/pull/288>`_) Add ``pymagicc.io.read_mag_file_metadata``, which allows fast reading of metadata from a ``.MAG`` file
- (`#290 <https://github.com/openscm/pymagicc/pull/290>`_) Update minimum ``scmdata`` version to v0.4.3
- (`#285 <https://github.com/openscm/pymagicc/pull/285>`_) Return ``pint.quantity.Quantity`` from all ECS, TCR and TCRE diagnostic methods
- (`#284 <https://github.com/openscm/pymagicc/pull/284>`_) Update ECS, TCR and TCRE diagnosis to use 1pctCO2 and abrupt-2xCO2 experiments
- (`#283 <https://github.com/openscm/pymagicc/pull/283>`_) Diagnose TCRE alongisde ECS and TCR, changes ``diagnose_tcr_ecs`` to ``diagnose_tcr_ecs_tcre`` and ``get_tcr_ecs_from_diagnosis_results`` method to ``get_tcr_ecs__tcre_from_diagnosis_results``
- (`#282 <https://github.com/openscm/pymagicc/pull/282>`_) Expose ``MAGICCBase.get_tcr_ecs_from_diagnosis_results`` method
- (`#280 <https://github.com/openscm/pymagicc/pull/280>`_) Also include source distribution in pypi release
- (`#271 <https://github.com/openscm/pymagicc/pull/271>`_) Update requirements of pyam, make error messages include ``stderr`` and remove overwrite of ``file_emisscen`` when creating MAGICC7 copies if ``not self.strict``
- (`#274 <https://github.com/openscm/pymagicc/pull/274>`_) Add better readers and writers for ``.DAT`` files
- (`#272 <https://github.com/openscm/pymagicc/pull/272>`_) Add support for new ``THISFILE_TIMESERIESTYPE`` in ``.MAG`` files
- (`#269 <https://github.com/openscm/pymagicc/pull/269>`_) Break circular dependency on OpenSCM by switching to using scmdata
- (`#268 <https://github.com/openscm/pymagicc/pull/268>`_) Update region mapping to match SSP database
- (`#266 <https://github.com/openscm/pymagicc/pull/266>`_) Use a whitelist of `OUT_` parameters which are converted to 1/0's
- (`#264 <https://github.com/openscm/pymagicc/pull/264>`_) Allowed an empty dataframe to be returned from ``MAGICCBase.run`` if no output is produced
- (`#267 <https://github.com/openscm/pymagicc/pull/267>`_) Hotfix appveyor failures
- (`#261 <https://github.com/openscm/pymagicc/pull/261>`_) Improve mapping of MAGICC7 to OpenSCM variables
- (`#259 <https://github.com/openscm/pymagicc/pull/259>`_) Added ``strict`` option for downgrading configuration exceptions to warnings
- (`#256 <https://github.com/openscm/pymagicc/pull/256>`_) Capture stderr output from MAGICC7 and above (not available in MAGICC6)
- (`#252 <https://github.com/openscm/pymagicc/pull/252>`_) Improve header writing, upgrade MAGICC time conversions and fix wine not installed error handling
- (`#253 <https://github.com/openscm/pymagicc/pull/253>`_) Add support for ``out_dynamic_vars`` parameter
- (`#250 <https://github.com/openscm/pymagicc/pull/250>`_) Add support for ``.MAG`` files
- (`#249 <https://github.com/openscm/pymagicc/pull/249>`_) Update to keep pace with MAGICC7 development
- (`#247 <https://github.com/openscm/pymagicc/pull/247>`_) Upgrade pyam dependency to use nominated release
- (`#244 <https://github.com/openscm/pymagicc/pull/244>`_) Use openscm from pip, hence drop Python3.6 support, and drop pyam dependency (moved into notebooks dependencies)
- (`#236 <https://github.com/openscm/pymagicc/pull/236>`_) Made all subannual files raise an InvalidTemporalResError exception as ScmDataFrame can't handle merging annual and subannual timeseries together yet
- (`#239 <https://github.com/openscm/pymagicc/pull/239>`_) Explicitly overwrite tuning model and emission scenario parameters for MAGICC7 when a temporary copy is created
- (`#229 <https://github.com/openscm/pymagicc/pull/229>`_) Add more robust tests of io, in particular that column order and spacing in files is preserved
- (`#233 <https://github.com/openscm/pymagicc/pull/233>`_) Fix inplace append hard coding as identified in `#232 <https://github.com/openscm/pymagicc/issues/232>`_
- (`#234 <https://github.com/openscm/pymagicc/pull/234>`_) Raise ``ValueError`` if ``only`` doesn't match an output variable in ``MAGICC.run`` (solves `#231 <https://github.com/openscm/pymagicc/issues/231>`_)
- (`#227 <https://github.com/openscm/pymagicc/pull/227>`_) Fixed up permafrost naming to avoid confusing inclusion when summing up "Emissions|CO2"
- (`#226 <https://github.com/openscm/pymagicc/pull/226>`_) Add ``SURFACE_TEMP.IN`` writer, closing `#211 <https://github.com/openscm/pymagicc/issues/211>`_
- (`#225 <https://github.com/openscm/pymagicc/pull/225>`_) Fix reading of ``DAT_CO2PF_EMIS.OUT``
- (`#224 <https://github.com/openscm/pymagicc/pull/224>`_) Add ``INVERSEEMIS.OUT`` reader
- (`#223 <https://github.com/openscm/pymagicc/pull/223>`_) Ensure `pymagicc.io._BinaryOutReader` closes the input file
- (`#222 <https://github.com/openscm/pymagicc/pull/222>`_) Remove trailing ``/`` in ``MANIFEST.IN`` recursive includes as this is invalid syntax on windows.
- (`#220 <https://github.com/openscm/pymagicc/pull/220>`_) If binary and ascii output files exist for a given variable only read the binary file
- (`#208 <https://github.com/openscm/pymagicc/pull/208>`_) Add set zero config method. Also adds scenarios module, tidies up the notebooks and adds a notebook showing how to run in different modes.
- (`#214 <https://github.com/openscm/pymagicc/pull/214>`_) Refactor to use the timeseries capabilities of ScmDataFrameBase
- (`#210 <https://github.com/openscm/pymagicc/pull/210>`_) Updated to match new openscm naming
- (`#199 <https://github.com/openscm/pymagicc/pull/199>`_) Switched to OpenSCMDataFrameBase for the backend, also includes:

  - dropping Python3.5 support as OpenSCM typing is not Python3.5 compatible
  - ensuring that metadata is properly stripped when reading
  - altering ``MAGICCData.append`` so that ``MAGICCData`` instances can be appended to ``MAGICCData`` instances
  - allowing the user to specify, ``model``, ``scenario`` and ``climate_model`` when initialising a ``MAGICCData`` instance
  - automatically filling ``model``, ``scenario`` and ``climate_model`` when running

- (`#204 <https://github.com/openscm/pymagicc/pull/204>`_) Addressed potential bug identified in (`#203 <https://github.com/openscm/pymagicc/issues/203>`_) and updated robustness of output file read in
- (`#198 <https://github.com/openscm/pymagicc/pull/198>`_) Move all install requirements into ``setup.py``
- (`#190 <https://github.com/openscm/pymagicc/pull/190>`_) Speed up diagnosis of TCR and ECS by removing writing of scenario file
- (`#191 <https://github.com/openscm/pymagicc/pull/191>`_) Fixed bugs which meant config passed to MAGICC wasn't handled correctly and renamed `tests/test_api.py` to `tests/test_core.py`.
- (`#187 <https://github.com/openscm/pymagicc/pull/187>`_) Added `pymagicc.io.join_timeseries` which simplifies joining/merging scenarios to create custom scenarios
- (`#185 <https://github.com/openscm/pymagicc/pull/185>`_) Added ability to read RCP files from http://www.pik-potsdam.de/~mmalte/rcps/ as requested in `#176 <https://github.com/openscm/pymagicc/issues/176>`_
- (`#184 <https://github.com/openscm/pymagicc/pull/184>`_) Remove redundant mapping of region names for SCEN to SCEN7 conversions
- (`#183 <https://github.com/openscm/pymagicc/pull/183>`_) Added ability to read MHALO files (see `#182 <https://github.com/openscm/pymagicc/issues/182>`_)
- (`#180 <https://github.com/openscm/pymagicc/pull/180>`_) Added reference which explains MAGICC's variables to docs
- (`#177 <https://github.com/openscm/pymagicc/pull/177>`_) Fixed SCEN reading bug, can now read SCEN files with "YEAR" in first column rather than "YEARS"
- (`#170 <https://github.com/openscm/pymagicc/pull/170>`_) Added pyam as a dependency and gave an example of how to integrate with it
- (`#173 <https://github.com/openscm/pymagicc/pull/173>`_) Renamed
  ``pymagicc.api`` to ``pymagicc.core``
- (`#168 <https://github.com/openscm/pymagicc/pull/168>`_) Added MAGICC7 compatibility
- (`#165 <https://github.com/openscm/pymagicc/pull/165>`_) Moved to one unified backend for all run functionality. This one got a bit out of hand so also includes:

  - Breaking the API, hence requiring significantly re-writing the tests to match the new API, bumping the major version number and updating the examples.
  - Locking up Pymagicc so that it will only run if MAGICC's ``.CFG`` files are configured in the simplest way possible (see :ref:`MAGICC flags`). This required re-writing the ``pymagicc/MAGICC6/run/MAGCFG_USER.CFG`` file that ships with Pymagicc (although the result is the same, as confirmed by the fact that the outputs of the four RCPs are unchanged in ``tests/test_pymagicc.py``).
  - Adding a function to pull a single configuration file from a MAGICC ``PARAMETERS.OUT`` file to aid the transition to the change referred to above (i.e. one could run MAGICC with whatever config elsewhere and then get a single config file which can be used with Pymagicc from the resulting ``PARAMETERS.OUT`` file).
  - Tidying up the docs to make linking a bit simpler and more reusable.
  - Only passing ``filepath`` (i.e. the combination of path and name) to reading/writing functions to remove ambiguity in previous language which used ``file``, ``filepath``, ``path``, ``name`` and ``filename``, sometimes in a self-contradictory way.

- (`#167 <https://github.com/openscm/pymagicc/pull/167>`_) Updated release instructions
- (`#162 <https://github.com/openscm/pymagicc/pull/162>`_) Added basic tests of integration with MAGICC binaries
- (`#163 <https://github.com/openscm/pymagicc/pull/163>`_) Confirmed HFC-245fa misnaming in MAGICC6. Accordingly, we:

  - fixed this naming in the SRES scenarios
  - removed ``pymagicc/MAGICC6/run/HISTRCP_HFC245ca_CONC.IN`` to avoid repeating this confusion
  - ensured that anyone who finds a file with "HFC-245ca" in it in future will get a warning, see ``tests/test_definitions.py``

- (`#164 <https://github.com/openscm/pymagicc/pull/164>`_) Improved missing MAGICC binary message in tests as discussed in `#124 <https://github.com/openscm/pymagicc/issues/124>`_
- (`#154 <https://github.com/openscm/pymagicc/pull/154>`_) Change to using OpenSCM variables for all user facing data as well as preparing to move to using OpenSCM dataframes

  - Note that this change breaks direct access but that we will gain a lot of features once we start using the capabilities of pyam as part of an OpenSCM dataframe

- (`#160 <https://github.com/openscm/pymagicc/pull/159>`_) Made notebooks CI more opinionated (`#158 <https://github.com/openscm/pymagicc/issues/158>`_)
- (`#139 <https://github.com/openscm/pymagicc/pull/139>`_) Added the ability to read all MAGICC output files/throw an explanatory error with ``pymagicc.io.MAGICCData``
- (`#135 <https://github.com/openscm/pymagicc/pull/135>`_) Moved emissions definitions to a single csv and packaged all of the definitions files using the `data package standard <https://frictionlessdata.io/docs/creating-tabular-data-packages-in-python/>`_
- (`#79 <https://github.com/openscm/pymagicc/pull/79>`_) Confirmed that keeping track of config state works and added example to TCR/ECS diagnosis notebook
- (`#146 <https://github.com/openscm/pymagicc/pull/146>`_) Removed path alteration from docs buiding
- (`#143 <https://github.com/openscm/pymagicc/pull/143>`_) Only read ``PARAMETERS.OUT`` file if it exists. ``MAGICCBase.config`` now defaults to ``None`` until a valid ``PARAMETERS.OUT`` file is read.
- (`#133 <https://github.com/openscm/pymagicc/pull/133>`_) Put definitions of MAGICC6's expected emissions into a standalone module
- (`#102 <https://github.com/openscm/pymagicc/pull/102>`_) Added ability to read and write SCEN7 files
- (`#108 <https://github.com/openscm/pymagicc/pull/108>`_) Added ability to read all files in MAGICC6 run folder (``pymagicc/MAGICC6/run``) to a common format
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
