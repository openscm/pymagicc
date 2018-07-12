<h1 id="pymagicc.input">pymagicc.input</h1>


<h2 id="pymagicc.input.MAGICCInput">MAGICCInput</h2>

```python
MAGICCInput(self, filename=None)
```

An interface to read and write the input files used by MAGICC.

MAGICCInput can read input files from both MAGICC6 and MAGICC7. It returns
files in a common format with a common vocabulary to simplify the process
of reading, writing and handling MAGICC data.

The MAGICCInput, once the target input file has been loaded, can be
treated as a Pandas DataFrame. All the methods available to a DataFrame
can be called on the MAGICCInput.

```python
with MAGICC6() as magicc:
    mdata = MAGICCInput('HISTRCP_CO2I_EMIS.IN')
    mdata.read(magicc.run_dir)
    mdata.plot()
```

TODO: Write example for writing

__Parameters__

- __filename (str)__: Name of the file to read

<h3 id="pymagicc.input.MAGICCInput.read">read</h3>

```python
MAGICCInput.read(self, filepath=None, filename=None)
```

Read an input file from disk

__Parameters__

- __filepath (str)__: The directory to file the file from. This is often the
    run directory for a magicc instance. If None is passed,
    the run directory for the bundled version of MAGICC6 is used.
- __filename (str)__: The filename to read. Overrides any existing values.

<h3 id="pymagicc.input.MAGICCInput.write">write</h3>

```python
MAGICCInput.write(self, filename)
```

TODO: Implement writing to disk

