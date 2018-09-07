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

<h2 id="pymagicc.api.MAGICC6">MAGICC6</h2>

```python
MAGICC6(self, root_dir=None)
```

<h2 id="pymagicc.api.MAGICC7">MAGICC7</h2>

```python
MAGICC7(self, root_dir=None)
```

