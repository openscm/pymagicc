from os.path import dirname, join

import pandas as pd

_dtrm = pd.read_csv(join(dirname(__file__), "magicc_dattype_regionmode_regions.csv"))

region_cols = _dtrm.columns.to_series().apply(lambda x: x.startswith("Region"))

dattype_regionmode_regions = _dtrm.loc[:, ~region_cols].copy()
dattype_regionmode_regions["Regions"] = [
    [r for r in raw if not pd.isnull(r)]
    for raw in _dtrm.loc[:, region_cols].values.tolist()
]

# TODO: put this text in docs/in data package with csv or something

# ------- SCEN emissions code definitions -------
# The definitions below define the emissions species which must be in SCEN (
# i.e. scenario i.e. emissions projection input) files and which emissions
# code they correspond to. The emissions code is used by MAGICC to
# pre-allocate arrays.

# ------- .prn species -------
# .prn files are MAGICC6's ozone depleting species input file. They must
# always contain the following species, regardless of whether they are
# providing concentration or emissions timeseries.




_emms_units = pd.read_csv(join(dirname(__file__), "magicc_emisssions_units.csv"))

def get_emissions_species(variable):
    exceptions = ["HCFC141B", "HCFC142B"]

    if variable in exceptions:
        return variable
    elif variable.endswith(("I", "B")):
        return variable[:-1]
    else:
        return variable

emms_units = _emms_units[["MAGICC variable", "emissions units"]]
emms_units["MAGICC variable"] = emms_units["MAGICC variable"].apply(get_emissions_species)
emms_units = emms_units.drop_duplicates()

scen_emms_code_1 = _emms_units[_emms_units["SCEN emms code 1"]]["MAGICC variable"].tolist()
scen_emms_code_0 = _emms_units[_emms_units["SCEN emms code 0"]]["MAGICC variable"].tolist()
prn_species = _emms_units[_emms_units["prn emms"]]["MAGICC variable"].tolist()


_concs_units = pd.read_csv(join(dirname(__file__), "magicc_concentrations_units.csv"))
