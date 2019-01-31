from os.path import dirname, join, abspath
from ..io import MAGICCData
from ..config import default_config


# path to load files from included package
_magicc6_included_distribution_path = dirname(default_config["EXECUTABLE_6"])


def read_scen_file(filepath, **kwargs):
    """
    Read a MAGICC .SCEN file.

    Parameters
    ----------
    filepath : str
        Filepath of the .SCEN file to read
    kwargs
        Passed to init method of MAGICCData

    Returns
    -------
    :obj:`pymagicc.io.MAGICCData`
        ``MAGICCData`` object containing the data and metadata.
    """
    mdata = MAGICCData(filepath, **kwargs)

    return mdata


rcp26 = read_scen_file(join(_magicc6_included_distribution_path, "RCP26.SCEN"), model="IMAGE", scenario="RCP26")
rcp45 = read_scen_file(join(_magicc6_included_distribution_path, "RCP45.SCEN"), model="MiniCAM", scenario="RCP45")
rcp60 = read_scen_file(join(_magicc6_included_distribution_path, "RCP60.SCEN"), model="AIM", scenario="RCP60")
rcp85 = read_scen_file(join(_magicc6_included_distribution_path, "RCP85.SCEN"), model="MESSAGE", scenario="RCP85")

scenarios = {"RCP26": rcp26, "RCP45": rcp45, "RCP60": rcp60, "RCP85": rcp85}

zero_emissions = MAGICCData(
    join(dirname(abspath(__file__)), "RCP3PD_EMISSIONS.DAT"),
    scenario="idealised",
    model="unspecified",
    climate_model="unspecified",
).filter(region="World")

zero_emissions.data.loc[:, "value"] = 0
