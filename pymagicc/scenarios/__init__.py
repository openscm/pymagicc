from os.path import dirname, join, abspath
from copy import deepcopy


from ..io import MAGICCData, read_scen_file
from ..config import default_config


# path to load files from included package
_magicc6_included_distribution_path = dirname(default_config["EXECUTABLE_6"])


rcp26 = read_scen_file(
    join(_magicc6_included_distribution_path, "RCP26.SCEN"),
    columns={"model": ["IMAGE"], "scenario": ["RCP26"]},
)
rcp45 = read_scen_file(
    join(_magicc6_included_distribution_path, "RCP45.SCEN"),
    columns={"model": ["MiniCAM"], "scenario": ["RCP45"]},
)
rcp60 = read_scen_file(
    join(_magicc6_included_distribution_path, "RCP60.SCEN"),
    columns={"model": ["AIM"], "scenario": ["RCP60"]},
)
rcp85 = read_scen_file(
    join(_magicc6_included_distribution_path, "RCP85.SCEN"),
    columns={"model": ["MESSAGE"], "scenario": ["RCP85"]},
)

rcps = deepcopy(rcp26)
for rcp in [rcp45, rcp60, rcp85]:
    rcps.append(rcp)

zero_emissions = MAGICCData(
    join(dirname(abspath(__file__)), "RCP3PD_EMISSIONS.DAT"),
    columns={
        "scenario": ["idealised"],
        "model": ["unspecified"],
        "climate_model": ["unspecified"],
    },
).filter(region="World")

zero_emissions._data[:] = 0
