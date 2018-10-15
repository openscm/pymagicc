"""
This module contains all of the relevant definitions for handling MAGICC data.

The definitions are given in `Data Packages <https://frictionlessdata.io/docs/
creating-tabular-data-packages-in-python/>`_. These store the data in an easy to read
CSV file whilst providing comprehensive metadata describing the data (column meanings
and expected types) in the accompanying ``datapackage.json`` file. Please see this
metadata for further details.

For more details about how these constants are used, see the documentation of
``pymagicc.io``. In particular, the documentation of
``pymagicc.io.get_special_scen_code``, ``pymagicc.io.get_dattype_regionmode`` and
``pymagicc.io.get_region_order``.
"""
from pathlib import Path


import pandas as pd
from pandas_datapackage_reader import read_datapackage


path = Path(__file__).parent


_dtrm = read_datapackage(path, "magicc_dattype_regionmode_regions")

_region_cols = _dtrm.columns.to_series().apply(lambda x: x.startswith("Region"))

dattype_regionmode_regions = _dtrm.loc[:, ~_region_cols].copy()
"""pandas.DataFrame: Mapping between regions and whether a file is SCEN7 or not and the expected values of THISFILE_DATTYPE and THISFILE_REGIONMODE flags in MAGICC.
"""

dattype_regionmode_regions["Regions"] = [
    [r for r in raw if not pd.isnull(r)]
    for raw in _dtrm.loc[:, _region_cols].values.tolist()
]

_emms_units = read_datapackage(path, "magicc_emisssions_units")

scen_emms_code_1 = _emms_units[_emms_units["SCEN emms code 1"]][
    "MAGICC variable"
].tolist()
"""list: The emissions which are included in a SCEN file if the SCEN emms code is 1.

See documentation of ``pymagicc.io.get_special_scen_code`` for more details.
"""

scen_emms_code_0 = _emms_units[_emms_units["SCEN emms code 0"]][
    "MAGICC variable"
].tolist()
"""list: The emissions which are included in a SCEN file if the SCEN emms code is 0.

See documentation of ``pymagicc.io.get_special_scen_code`` for more details.
"""

prn_species = _emms_units[_emms_units["prn emms"]]["MAGICC variable"].tolist()
"""list: The emissions which are included in a ``.prn`` file.
"""

_concs_units = read_datapackage(path, "magicc_concentrations_units")
