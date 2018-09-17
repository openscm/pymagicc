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

magicc6_emms_code_all_emissions = [
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

magicc6_emms_code_0_emissions_extra = ["C4F10"]
magicc6_emms_code_0_emissions = (
    magicc6_emms_code_all_emissions + magicc6_emms_code_0_emissions_extra
)

magicc6_emms_code_1_emissions_extra = ["BC", "OC", "NH3", "C6F14"]
magicc6_emms_code_1_emissions = (
    magicc6_emms_code_all_emissions + magicc6_emms_code_1_emissions_extra
)

magicc6_prn_species = [
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
