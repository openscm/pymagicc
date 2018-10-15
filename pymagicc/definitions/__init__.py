"""
This module contains all of the relevant definitions for handling MAGICC data.

The definitions are given in `data packages <https://frictionlessdata.io/docs/
creating-tabular-data-packages-in-python/>`_. These store the data in an easy to read
csv file whilst providing comprehensive metadata in the accompanying
``datapackage.json`` file.


Attributes
----------

scen_emms_code_1 : list


see documentation of `pymagicc/io.py::_ScenWriter.get_special_scen_code` for further explanation
"""

from pathlib import Path
import pandas as pd
from pandas_datapackage_reader import read_datapackage

path = Path(__file__).parent


_dtrm = read_datapackage(path, "magicc_dattype_regionmode_regions")

region_cols = _dtrm.columns.to_series().apply(lambda x: x.startswith("Region"))

dattype_regionmode_regions = _dtrm.loc[:, ~region_cols].copy()
dattype_regionmode_regions["Regions"] = [
    [r for r in raw if not pd.isnull(r)]
    for raw in _dtrm.loc[:, region_cols].values.tolist()
]

_emms_units = read_datapackage(path, "magicc_emisssions_units")

scen_emms_code_1 = _emms_units[_emms_units["SCEN emms code 1"]]["MAGICC variable"].tolist()
scen_emms_code_0 = _emms_units[_emms_units["SCEN emms code 0"]]["MAGICC variable"].tolist()
prn_species = _emms_units[_emms_units["prn emms"]]["MAGICC variable"].tolist()


_concs_units = read_datapackage(path, "magicc_concentrations_units")
