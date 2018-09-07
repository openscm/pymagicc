<h1 id="pymagicc.input">pymagicc.input</h1>


<h2 id="pymagicc.input.InputReader">InputReader</h2>

```python
InputReader(self, filename)
```

<h3 id="pymagicc.input.InputReader.header_tags">header_tags</h3>

list() -> new empty list
list(iterable) -> new list initialized from iterable's items
<h3 id="pymagicc.input.InputReader.process_data">process_data</h3>

```python
InputReader.process_data(self, stream, metadata)
```

Extract the tabulated data from the input file

__Arguments__

- __stream (Streamlike object)__: A Streamlike object (nominally StringIO)
    containing the table to be extracted
- __metadata (dict)__: metadata read in from the header and the namelist

__Returns__

`df (pandas.DataFrame)`: contains the data, processed to the standard
    MAGICCInput format
`metadata (dict)`: updated metadata based on the processing performed

<h3 id="pymagicc.input.InputReader.process_header">process_header</h3>

```python
InputReader.process_header(self, header)
```

Parse the header for additional metadata

__Arguments__

- __header (str)__: all the lines in the header

__Returns__

`return (dict)`: the metadata in the header

<h2 id="pymagicc.input.InputWriter">InputWriter</h2>

```python
InputWriter(self)
```

<h3 id="pymagicc.input.InputWriter.write">write</h3>

```python
InputWriter.write(self, magicc_input, filename, filepath=None)
```

Write a MAGICC input file from df and metadata

__Arguments__

- __magicc_input (MAGICCInput)__: a MAGICCInput object which holds the data
    to write
- __filename (str)__: name of file to write to
- __filepath (str)__: path in which to write file. If not provided,
- __the file will be written in the current directory (TODO__: check this is true...)

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
MAGICCInput.write(self, filename, filepath=None)
```

TODO: Implement writing to disk

