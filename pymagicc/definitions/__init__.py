from os.path import dirname, join

import pandas as pd

_dtrm = pd.read_csv(
    join(dirname(__file__), 'magicc_dattype_regionmode_regions.csv')
)

region_cols = _dtrm.columns.to_series().apply(
    lambda x: x.startswith('Region')
)

dattype_regionmode_regions = _dtrm.loc[:, ~region_cols].copy()
dattype_regionmode_regions['Regions'] = [
    [r for r in raw if not pd.isnull(r)]
    for raw in _dtrm.loc[:, region_cols].values.tolist()
]

emissions_units = {}
concentrations_units = {}
