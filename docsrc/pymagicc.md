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

