# pymagicc

| [![Build Status](https://img.shields.io/travis/openclimatedata/pymagicc.svg)](https://travis-ci.org/openclimatedata/pymagicc) | [![AppVeyor](https://img.shields.io/appveyor/ci/openclimatedata/pymagicc.svg)](https://ci.appveyor.com/project/openclimatedata/pymagicc) |
| :--- | :--- |
| [![Codecov](https://img.shields.io/codecov/c/github/openclimatedata/pymagicc.svg)](https://codecov.io/gh/openclimatedata/pymagicc) | [![Launch Binder](https://img.shields.io/badge/launch-binder-e66581.svg)](https://mybinder.org/v2/gh/openclimatedata/pymagicc/master?filepath=notebooks/Example.ipynb) |
| [![PyPI](https://img.shields.io/pypi/pyversions/pymagicc.svg)](https://pypi.python.org/pypi/pymagicc) | [![PyPI](https://img.shields.io/pypi/v/pymagicc.svg)](https://pypi.python.org/pypi/pymagicc) |
| [![status](https://joss.theoj.org/papers/85eb9a9401fe968073bb429ea361924e/status.svg)](https://joss.theoj.org/papers/85eb9a9401fe968073bb429ea361924e) | [![Zenodo](https://zenodo.org/badge/DOI/10.5281/zenodo.1111815.svg)](https://zenodo.org/record/1111815) |

Pymagicc is a thin Python wrapper around the reduced complexity climate model
[MAGICC6](http://magicc.org/). It wraps the CC-BY-NC-SA licensed
[MAGICC6 binary](http://www.magicc.org/download6).

Pymagicc makes the MAGICC model easily installable and usable from Python and can for example be used in the analysis of mitigation scenarios, in integrated assessment models, complex climate model emulation, and uncertainty analyses.

See http://www.magicc.org/ for further information about the MAGICC model.

## Basic Usage

```python
import pymagicc
from pymagicc import scenarios
import matplotlib.pyplot as plt

for name, scen in scenarios.items():
    results, params = pymagicc.run(scen, return_config=True)
    temp = (results["SURFACE_TEMP"].GLOBAL.loc[1850:] -
            results["SURFACE_TEMP"].GLOBAL.loc[1850:1900].mean())
    temp.plot(label=name)
plt.legend()
plt.title("Global Mean Temperature Projection")
plt.ylabel(u"°C over pre-industrial (1850-1900 mean)")
# Run `plt.show()` to display the plot when running this example
# interactively or add `%matplotlib inline` on top when in a Jupyter Notebook.
```

![](scripts/example-plot.png)


## Installation

    pip install pymagicc

On Linux and OS X the original compiled Windows binary available on
http://www.magicc.org/ and included in Pymagicc
can run using [Wine](https://www.winehq.org/).

On modern 64-bit systems one needs to use the 32-bit version of Wine

    sudo dpkg --add-architecture i386
    sudo apt-get install wine32

On 32-bit systems Debian/Ubuntu-based systems `wine` can be installed with

    sudo apt-get install wine

On OS X `wine` is available in the Homebrew package manager:

    brew install wine

Note that after the first install the first run of Pymagicc might be slow due
to setting up of the `wine` configuration and be accompanied by pop-ups or
debug output.

To run an example session using Jupyter Notebook and Python 3 you can run the
following commands to create a virtual environment `venv` and install an
editable version for local development:

    git clone https://github.com/openclimatedata/pymagicc.git

    cd pymagicc
    make venv
    ./venv/bin/pip install -e .
    ./venv/bin/jupyter-notebook notebooks/Example.ipynb


## Development

For local development run

    make venv
    ./venv/bin/pip install --editable .

inside of a clone or download of the Pymagicc repository
to install dependencies and and an editable version of Pymagicc.

To run the tests run

    ./venv/bin/pytest tests --verbose

To get a test coverage report, run

    ./venv/bin/pytest --cov


## More Usage Examples

### Use an included scenario

```python
from pymagicc import rcp3pd

rcp3pd["WORLD"].head()
```

### Read a MAGICC scenario file

```python
from pymagicc import read_scen_file

scenario = read_scen_file("PATHWAY.SCEN")
```

### Create a new scenario

Pymagicc uses Pandas DataFrames to represent scenarios. Dictionaries are
used for scenarios with multiple regions.

```python
import pandas as pd

scenario = pd.DataFrame({
    "FossilCO2": [8, 10, 9],
    "OtherCO2": [1.2, 1.1, 1.2],
    "CH4": [300, 250, 200]},
    index=[2010, 2020, 2030]
)

```

### Run MAGICC for a scenario

```python
output = pymagicc.run(scenario)

# Projected temperature adjusted to pre-industrial mean
temp = (output["SURFACE_TEMP"].GLOBAL -
        output["SURFACE_TEMP"].loc[1850:2100].GLOBAL.mean())
```

### Using a different MAGICC version

The `_magiccpath` and `_magiccbinary` can be changed to point to different MAGICC
development versions.

```python
pymagicc._magiccpath = "/home/robert/openclimatedata/pymagicc/MAGICC_test/"
pymagicc._magiccbinary = "./magicc"
```


## API

<h3 id="pymagicc">pymagicc</h3>


<h4 id="pymagicc.read_scen_file">read_scen_file</h4>

```python
read_scen_file(scen_file)
```

Reads a MAGICC .SCEN file and returns a
a dictionary of DataFrames or, for World Only scenarios, a DataFrame.

<h4 id="pymagicc.run">run</h4>

```python
run(scenario, output_dir=None, return_config=False, **kwargs)
```

Return output data and (optionally) used parameters from a MAGICC run.

##### Parameters

```
output_dir:
    Path for MAGICC data and binary, if None a temp file which will be
    deleted automatically.
return_config:
    Additionaly return the full list of parameters used. default False
kwargs:
    Parameters overwriting default parameters.
```

##### Returns

```
output: dict
    Dictionary with all data from MAGICC output files.
parameters: dict
    Parameters used in the MAGICC run. Only returned when
    ``return_config`` is set to True
```

<h4 id="pymagicc.write_scen_file">write_scen_file</h4>

```python
write_scen_file(scenario, path_or_buf=None, description1=None, description2=None, comment=None)
```

Write a Dictionary of DataFrames or DataFrame to a MAGICC .SCEN-file.

##### Parameters

```
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
```

## License

The [compiled MAGICC binary](http://www.magicc.org/download6) by Tom Wigley,
Sarah Raper, and Malte Meinshausen included in this package is licensed under a [Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported License](https://creativecommons.org/licenses/by-nc-sa/3.0/).


The `pymagicc` wrapper is free software under the GNU Affero General Public
License v3, see [LICENSE](./LICENSE).

If you make any use of MAGICC, please cite:

> M. Meinshausen, S. C. B. Raper and T. M. L. Wigley (2011). "Emulating coupled
atmosphere-ocean and carbon cycle models with a simpler model, MAGICC6: Part I
"Model Description and Calibration." Atmospheric Chemistry and Physics 11: 1417-1456.
[doi:10.5194/acp-11-1417-2011](https://dx.doi.org/10.5194/acp-11-1417-2011)

See also the [MAGICC website](http://magicc.org/) and
[Wiki](http://wiki.magicc.org/index.php?title=Main_Page)
for further information.
