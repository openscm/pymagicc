from copy import deepcopy
from os.path import abspath, dirname, join

from pymagicc.config import default_config
from pymagicc.io import MAGICCData

# path to load files from included package
_magicc6_included_distribution_path = dirname(default_config["EXECUTABLE_6"])


def read_scen_file(
    filepath,
    columns={
        "model": ["unspecified"],
        "scenario": ["unspecified"],
        "climate_model": ["unspecified"],
    },
    **kwargs
):
    """
    Read a MAGICC .SCEN file.

    Parameters
    ----------
    filepath : str
        Filepath of the .SCEN file to read

    columns : dict
        Passed to ``__init__`` method of MAGICCData. See
        ``MAGICCData.__init__`` for details.

    kwargs
        Passed to ``__init__`` method of MAGICCData. See
        ``MAGICCData.__init__`` for details.

    Returns
    -------
    :obj:`pymagicc.io.MAGICCData`
        ``MAGICCData`` object containing the data and metadata.
    """
    mdata = MAGICCData(filepath, columns=columns, **kwargs)

    return mdata


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
    rcps = rcps.append(rcp)

zero_emissions = MAGICCData(
    join(dirname(abspath(__file__)), "RCP3PD_EMISSIONS.DAT"),
    columns={
        "scenario": ["idealised"],
        "model": ["unspecified"],
        "climate_model": ["unspecified"],
    },
).filter(region="World")

zero_emissions = zero_emissions * 0.0
