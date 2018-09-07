<h1 id="pymagicc">pymagicc</h1>


<h2 id="pymagicc.read_scen_file">read_scen_file</h2>

```python
read_scen_file(scen_file)
```

Read a MAGICC .SCEN file

__Parameters__

- __scen_file (str)__: Path to scen_file to read

__Returns__

`output (DataFrame or Dict of DataFrames)`: For World only scenarios, a
single DataFrame with the data from the SCEN file. For scenarios with more
than one region, a dictionary containing one DataFrame for each region.

<h2 id="pymagicc.write_scen_file">write_scen_file</h2>

```python
write_scen_file(scenario, path_or_buf=None, description1=None, description2=None, comment=None)
```

Write a Dictionary of DataFrames or a DataFrame to a MAGICC `.SCEN` file.

Note that it is assumed that your units match the ones which are defined
in the units variable. This function provides no ability to convert units
or read units from a DataFrame attribute or column.

__Parameters__

- __scenario (DataFrame or Dict of DataFrames)__: If a single DataFrame is
    supplied, the data is assumed to be for the WORLD region. If a Dict of
    DataFrames is supplied then it is assumed that each DataFrame
    containes data for one region.
- __path_or_buf (str or buffer)__: Pathname or file-like object to which to write
    the scenario.
- __description_1 (str)__: Optional description line.
- __description_2 (str)__: Optional second description line.
- __comment(str)__: Optional comment at end of scenario file.

<h2 id="pymagicc.run">run</h2>

```python
run(scenario, return_config=False, **kwargs)
```

Run a MAGICC scenario and return output data and (optionally) config parameters

__Parameters__

- __return_config (bool)__: If True, return the full list of parameters used. default False
- __kwargs__:
    Parameters overwriting default parameters.

__Returns__

`output (dict)`: Dictionary with all data from the MAGICC output files in
    DataFrames
`parameters (dict)`: Parameters used in the MAGICC run. Only returned when
    `return_config` is set to True

<h1 id="pymagicc.api">pymagicc.api</h1>


<h2 id="pymagicc.api.MAGICCBase">MAGICCBase</h2>

```python
MAGICCBase(self, root_dir=None)
```

Provides access to the MAGICC binary and configuration.

To enable multiple MAGICC 'setups' to be configured independently,
the MAGICC directory containing the input files, configuration
and binary is copied to a new folder. The configuration in this
MAGICC copy can then be edited without impacting other instances or your
original MAGICC distribution.

A `MAGICC` instance first has to be setup by calling
`create_copy`. If many model runs are being performed this step only has
to be performed once. The `run` method can then be called many times
without re-copying the files each time. Between each call to `run`, the
configuration files can be updated to perform runs with different
configurations.

__Parameters__

- __root_dir (str)__: If `root_dir` is supplied, an existing MAGICC 'setup' is
    used.

<h1 id="pymagicc.io">pymagicc.io</h1>


<h2 id="pymagicc.io.MAGICCData">MAGICCData</h2>

```python
MAGICCData(self, filename=None)
```

An interface to read and write the input files used by MAGICC.

MAGICCData can read input files from both MAGICC6 and MAGICC7. It returns
files in a common format with a common vocabulary to simplify the process
of reading, writing and handling MAGICC data.

The MAGICCData, once the target input file has been loaded, can be
treated as a Pandas DataFrame. All the methods available to a DataFrame
can be called on the MAGICCData.

```python
with MAGICC6() as magicc:
    mdata = MAGICCData('HISTRCP_CO2I_EMIS.IN')
    mdata.read(magicc.run_dir)
    mdata.plot()
```

TODO: Write example for writing

__Parameters__

- __filename (str)__: Name of the file to read

<h3 id="pymagicc.io.MAGICCData.read">read</h3>

```python
MAGICCData.read(self, filepath=None, filename=None)
```

Read an input file from disk

__Parameters__

- __filepath (str)__: The directory to file the file from. This is often the
    run directory for a magicc instance. If None is passed,
    the run directory for the bundled version of MAGICC6 is used.
- __filename (str)__: The filename to read. Overrides any existing values.

<h3 id="pymagicc.io.MAGICCData.write">write</h3>

```python
MAGICCData.write(self, filename)
```

TODO: Implement writing to disk

<h1 id="pymagicc.config">pymagicc.config</h1>


Module for collating configuration variables from various sources

The order of preference is:
Overrides > Environment variable > Defaults

Overrides can be set using the ConfigStore

