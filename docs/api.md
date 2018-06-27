<h1 id="pymagicc">pymagicc</h1>


<h2 id="pymagicc.read_scen_file">read_scen_file</h2>

```python
read_scen_file(scen_file)
```

Reads a MAGICC .SCEN file and returns a
a dictionary of DataFrames or, for World Only scenarios, a DataFrame.

<h2 id="pymagicc.write_scen_file">write_scen_file</h2>

```python
write_scen_file(scenario, path_or_buf=None, description1=None, description2=None, comment=None)
```

Write a Dictionary of DataFrames or DataFrame to a MAGICC .SCEN-file.

Parameters
----------
scenario: DataFrame or Dict of DataFrames
    DataFrame (for scenarios with only the World region) or Dictionary with
    regions.
path_or_buf:
    Pathname or file-like object to write the scenario to.
description_1:
    Optional description line.
description_2:
    Optional second description line.
comment:
    Optional comment at end of scenario file.


<h2 id="pymagicc.run">run</h2>

```python
run(scenario, return_config=False, **kwargs)
```

Return output data and (optionally) used parameters from a MAGICC run.

Parameters
----------
return_config:
    Additionaly return the full list of parameters used. default False
kwargs:
    Parameters overwriting default parameters.

Returns
-------
output: dict
    Dictionary with all data from MAGICC output files.
parameters: dict
    Parameters used in the MAGICC run. Only returned when
    ``return_config`` is set to True

<h1 id="pymagicc.api">pymagicc.api</h1>


<h2 id="pymagicc.api.MAGICCBase">MAGICCBase</h2>

```python
MAGICCBase(self, root_dir=None)
```

Provides access to the MAGICC binary and configuration.

To enable multiple MAGICC 'packages' to be configured independently,
the MAGICC directory containing the input files, configuration
and binary is copied to a new folder. The configuration in this
MAGICC copy can then be edited without impacting other instances.

A `MAGICC` instance first has to be setup by calling
`create_copy`. If many model runs are being performed this step only has
to be performed once. `run` can be called many times with the
configuration files being updated between each call.

Alternatively, an existing MAGICC directory structure can be used by
setting `root_dir`.

<h1 id="pymagicc.input">pymagicc.input</h1>


<h2 id="pymagicc.input.MAGICCInput">MAGICCInput</h2>

```python
MAGICCInput(self, filename=None)
```

An interface to read (and in future write) the input files used by MAGICC.

MAGICCInput can read input files from both MAGICC6 and MAGICC7. These
include files with extensions .IN and .SCEN7.

The MAGICCInput, once the target input file has been loaded, can be
 treated as a pandas DataFrame. All the methods available to a DataFrame
 can be called on the MAGICCInput.


>>> with MAGICC6() as magicc:
>>>     mdata = MAGICCInput('HISTRCP_CO2I_EMIS.IN')
>>>     mdata.read(magicc.run_dir)
>>>     mdata.plot()

<h1 id="pymagicc.config">pymagicc.config</h1>


Module for collating configuration variables from various sources

The order of preference is:
Overrides > Environment variable > Defaults

