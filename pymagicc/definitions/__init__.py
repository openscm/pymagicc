from os.path import dirname, join

import pandas as pd

_dtrm = pd.read_csv(join(dirname(__file__), "magicc_dattype_regionmode_regions.csv"))

region_cols = _dtrm.columns.to_series().apply(lambda x: x.startswith("Region"))

dattype_regionmode_regions = _dtrm.loc[:, ~region_cols].copy()
dattype_regionmode_regions["Regions"] = [
    [r for r in raw if not pd.isnull(r)]
    for raw in _dtrm.loc[:, region_cols].values.tolist()
]

# TODO: do read ins for these too
emissions_units = {}
concentrations_units = {}

# ------- SCEN emissions code definitions -------
# The definitions below define the emissions species which must be in SCEN (
# i.e. scenario i.e. emissions projection input) files and which emissions
# code they correspond to. The emissions code is used by MAGICC to
# pre-allocate arrays.

# The emissions species which must be included in all SCEN files
scen_emms_base = [
    "CO2I",
    "CO2B",
    "CH4",
    "N2O",
    "SOX",
    "CO",
    "NMVOC",
    "NOX",
    "CF4",
    "C2F6",
    "HFC23",
    "HFC32",
    "HFC4310",
    "HFC125",
    "HFC134A",
    "HFC143A",
    "HFC227EA",
    "HFC245FA",
    "SF6",
]


scen_emms_code_0_extra = ["C4F10"]
# The emissions species which give a SCEN emissions code of 0
scen_emms_code_0 = scen_emms_base + scen_emms_code_0_extra

scen_emms_code_1_extra = ["BC", "OC", "NH3", "C6F14"]
# The emissions species which give a SCEN emissions code of 1
scen_emms_code_1 = scen_emms_base + scen_emms_code_1_extra

# ------- End SCEN emissions code definitions -------


# ------- .prn species -------
# .prn files are MAGICC6's ozone depleting species input file. They must
# always contain the following species, regardless of whether they are
# providing concentration or emissions timeseries.
prn_species = [
    "CFC11",
    "CFC12",
    "CFC113",
    "CFC114",
    "CFC115",
    "CCL4",
    "CH3CCL3",
    "HCFC22",
    "HCFC141B",
    "HCFC142B",
    "HALON1211",
    "HALON1202",
    "HALON1301",
    "HALON2402",
    "CH3BR",
    "CH3CL",
]
# ------- End .prn species -------
