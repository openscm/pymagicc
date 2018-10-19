# Copyright (c) 2017 pymagicc authors:
#   Robert Gieseke <robert.gieseke@pik-potsdam.de>
# Free software under GNU Affero General Public License v3, see LICENSE
#
# The compiled MAGICC binary (http://www.magicc.org/download6) by Tom Wigley,
# Sarah Raper, and Malte Meinshausen included in this package is licensed under
# a Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported
# License (https://creativecommons.org/licenses/by-nc-sa/3.0/)


import logging
import os
import subprocess

import f90nml
import pandas as pd

from ._version import get_versions
from .config import config as _config
from .api import MAGICC6, MAGICC7  # noqa
from .io import MAGICCData
from .utils import get_date_time_string

__version__ = get_versions()["version"]
del get_versions

# Path used for data files loading.
_magiccpath = MAGICC6().original_dir

if not _config["is_windows"]:
    wine_installed = (
        subprocess.call(
            "type wine", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        == 0
    )
    if not wine_installed:
        logging.warning("Wine is not installed")


################################################################################
### ---- to be deleted I think --------------------------------------------- ###
# config should be used by magicc instances and should live elsewhere
_config_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "default_config.nml"
)
default_config = f90nml.read(_config_path)
### ------------------------------------------------------------------------ ###
################################################################################


def read_scen_file(filepath):
    """
    Read a MAGICC .SCEN file.

    Parameters
    ----------
    filepath : str
        Filepath of the .SCEN file to read

    Returns
    -------
    :obj:`pymagicc.io.MAGICCData`
        ``MAGICCData`` object containing the data and metadata.
    """
    mdata = MAGICCData()
    mdata.read(filepath)

    return mdata

rcp26 = read_scen_file(os.path.join(_magiccpath, "RCP26.SCEN"))
rcp45 = read_scen_file(os.path.join(_magiccpath, "RCP45.SCEN"))
rcp60 = read_scen_file(os.path.join(_magiccpath, "RCP60.SCEN"))
rcp85 = read_scen_file(os.path.join(_magiccpath, "RCP85.SCEN"))

scenarios = {"RCP26": rcp26, "RCP45": rcp45, "RCP60": rcp60, "RCP85": rcp85}


def run(scenario, magicc_version=6, **kwargs):
    """
    Run a MAGICC scenario and return output data and (optionally) config parameters.

    Parameters
    ----------
    scenario : :obj:`pymagicc.io.MAGICCData`
        Scenario to run

    magicc_version : int
        MAGICC version to use for the run

    return_config : bool
        If True, return the full list of parameters used

    kwargs
        Parameters overwriting default parameters

    Raises
    ------
    ValueError
        If the magicc_version is not available

    Returns
    -------
    output : :obj:`pymagicc.io.MAGICCData`
        Output of the run with the data in the ``df`` attribute and parameters and
        other metadata in the ``metadata attribute``
    """
    if magicc_version == 6:
        magicc_cls = MAGICC6
    elif magicc_version == 7:
        magicc_cls = MAGICC7
    else:
        raise ValueError("MAGICC version {} is not available".format(magicc_version))

    with magicc_cls() as magicc:
        ###############################################################################
        # nasty, should be able to do this better within MAGICCBase class
        if magicc.executable is None:
            raise ValueError("MAGICC executable not found, try setting an environment variable `MAGICC_EXECUTABLE_{}=/path/to/binary`".format(magicc_version))



        year_cfg = {}
        if "startyear" in kwargs:
            year_cfg["startyear"] = kwargs.pop("startyear")
        if "endyear" in kwargs:
            year_cfg["endyear"] = kwargs.pop("endyear")
        magicc.set_years(**year_cfg)

        # should be able to do some other nice metadata stuff here
        kwargs.setdefault("rundate", get_date_time_string())
        magicc.set_config(**kwargs)
        ################################################################################

        results = magicc.run()
