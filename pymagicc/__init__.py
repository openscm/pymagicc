# Copyright (c) 2017 pymagicc authors:
#   Robert Gieseke <robert.gieseke@pik-potsdam.de>
# Free software under GNU Affero General Public License v3, see LICENSE
#
# The compiled MAGICC binary (http://www.magicc.org/download6) by Tom Wigley,
# Sarah Raper, and Malte Meinshausen included in this package is licensed under
# a Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported
# License (https://creativecommons.org/licenses/by-nc-sa/3.0/)


import datetime
import linecache
import logging
import os
import subprocess

import f90nml
import pandas as pd

from ._version import get_versions
from .config import config as _config
from .api import MAGICC6, MAGICC7  # noqa

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

_config_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "default_config.nml"
)
default_config = f90nml.read(_config_path)

# MAGICC's SCEN files encode the regions as follows.
region_codes = {
    11: ["WORLD"],
    20: ["WORLD", "OECD90", "REF", "ASIA", "ALM"],
    21: ["WORLD", "OECD90", "REF", "ASIA", "ALM"],
    31: ["WORLD", "R5OECD", "R5REF", "R5ASIA", "R5MAF", "R5LAM"],
    41: ["WORLD", "R5OECD", "R5REF", "R5ASIA", "R5MAF", "R5LAM", "BUNKERS"],
}

# Order of columns to use when writing SCEN files.
_columns = [
    "YEARS",
    "FossilCO2",
    "OtherCO2",
    "CH4",
    "N2O",
    "SOx",
    "CO",
    "NMVOC",
    "NOx",
    "BC",
    "OC",
    "NH3",
    "CF4",
    "C2F6",
    "C6F14",
    "HFC23",
    "HFC32",
    "HFC43-10",
    "HFC125",
    "HFC134a",
    "HFC143a",
    "HFC227ea",
    "HFC245fa",
    "SF6",
]

# Units to be used for each column.
units = {
    "BC": "Mt",
    "C2F6": "kt",
    "C6F14": "kt",
    "CF4": "kt",
    "CH4": "MtCH4",
    "CO": "MtCO",
    "FossilCO2": "GtC",
    "HFC125": "kt",
    "HFC134a": "kt",
    "HFC143a": "kt",
    "HFC227ea": "kt",
    "HFC23": "kt",
    "HFC245fa": "kt",
    "HFC32": "kt",
    "HFC43-10": "kt",
    "N2O": "MtN2O-N",
    "NH3": "MtN",
    "NMVOC": "Mt",
    "NOx": "MtN",
    "OC": "Mt",
    "OtherCO2": "GtC",
    "SF6": "kt",
    "SOx": "MtS",
    "YEARS": "Yrs",
}


def _get_number_of_datapoints(scen_file):
    """Return number of timeseries datapoints from a .SCEN-file."""
    return int(linecache.getline(scen_file, 1))


def _get_region_code(scen_file):
    """Return region code for a .SCEN-file."""
    return int(linecache.getline(scen_file, 2))


def read_scen_file(scen_file):
    """
    Read a MAGICC .SCEN file

    # Parameters
    scen_file (str): Path to scen_file to read

    # Returns
    output (DataFrame or Dict of DataFrames): For World only scenarios, a
    single DataFrame with the data from the SCEN file. For scenarios with more
    than one region, a dictionary containing one DataFrame for each region.
    """
    num_datapoints = _get_number_of_datapoints(scen_file)

    region_code = _get_region_code(scen_file)
    regions = region_codes[region_code]

    output = {}

    for idx, region in enumerate(regions):
        skip = num_datapoints * idx + 5 * idx
        skiprows = list(range(7 + skip)) + [8 + skip]

        output[region] = pd.read_csv(
            scen_file,
            delimiter=r"\s+",
            skiprows=skiprows,
            nrows=num_datapoints,
            header=0,
            index_col=0,
        )
        output[region].name = region

    if region_code == 11:
        return output["WORLD"]
    else:
        return output


rcp26 = read_scen_file(os.path.join(_magiccpath, "RCP26.SCEN"))
rcp45 = read_scen_file(os.path.join(_magiccpath, "RCP45.SCEN"))
rcp60 = read_scen_file(os.path.join(_magiccpath, "RCP60.SCEN"))
rcp85 = read_scen_file(os.path.join(_magiccpath, "RCP85.SCEN"))

scenarios = {"RCP26": rcp26, "RCP45": rcp45, "RCP60": rcp60, "RCP85": rcp85}


def _get_date_time_string():
    """Return a timestamp with current date and time."""
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d %H:%M")


def write_scen_file(
    scenario, path_or_buf=None, description1=None, description2=None, comment=None
):
    """
    Write a Dictionary of DataFrames or a DataFrame to a MAGICC `.SCEN` file.

    Note that it is assumed that your units match the ones which are defined
    in the units variable. This function provides no ability to convert units
    or read units from a DataFrame attribute or column.

    # Parameters
    scenario (DataFrame or Dict of DataFrames): If a single DataFrame is
        supplied, the data is assumed to be for the WORLD region. If a Dict of
        DataFrames is supplied then it is assumed that each DataFrame
        containes data for one region.
    path_or_buf (str or buffer): Pathname or file-like object to which to write
        the scenario.
    description_1 (str): Optional description line.
    description_2 (str): Optional second description line.
    comment(str): Optional comment at end of scenario file.
    """

    if not isinstance(scenario, dict):
        scenario = dict({"WORLD": scenario})

    delim = "\n"

    out = []

    num_datapoints = len(scenario["WORLD"])

    # Number of datapoints for each timeseries.
    out.append(" " + str(num_datapoints))

    # Regions.
    num_regions = len(scenario)
    for region_code, regions in region_codes.items():
        if len(regions) == num_regions:
            out.append(" " + str(region_code))
            break

    # Scenario name.
    if isinstance(path_or_buf, str):
        name = os.path.basename(path_or_buf.replace(".SCEN", ""))
    else:
        name = "MAGICC Scenario"
    out.append(" " + name)

    # Description
    if not description1:
        description1 = "Generated scenario."
    out.append(" " + description1)

    if not description2:
        description2 = "DATE: " + _get_date_time_string()
    out.append(" " + description2)

    out.append("")

    with_padding = "{0: >11}"
    with_digits = "{0: >11.4f}"

    # Regions.
    for region in region_codes[region_code]:
        out.append(" " + region)

        # Header line.
        header_line = [with_padding.format(_columns[0])]

        for column in _columns:
            if column in scenario[region].columns:
                header_line.append(with_padding.format(column))
        out.append("".join(header_line))

        # Unit line.
        units_line = [with_padding.format(units[_columns[0]])]
        for column in _columns[1:]:
            if column in scenario[region].columns:
                units_line.append(with_padding.format(units[column]))
        out.append("".join(units_line))

        # Data lines for each year.
        for year in scenario[region].index:
            data = [with_padding.format(year)]
            for column in _columns[1:]:
                if column in scenario[region].columns:
                    data.append(with_digits.format(scenario[region].loc[year][column]))
            out.append("".join(data))

        # Two empty lines after each block.
        out.append("")
        out.append("")
    out.append("")

    # Final (optional) comment.
    if comment:
        out.append(comment)

    scenfile_content = delim.join(out)

    if isinstance(path_or_buf, str):
        with open(path_or_buf, "w") as f:
            f.write(scenfile_content)
    elif path_or_buf and path_or_buf.write:
        path_or_buf.write(scenfile_content)
    else:
        return scenfile_content


def run(scenario, return_config=False, **kwargs):
    """
    Run a MAGICC scenario and return output data and (optionally) config parameters

    # Parameters
    return_config (bool): If True, return the full list of parameters used. default False
    kwargs:
        Parameters overwriting default parameters.

    # Returns
    output (dict): Dictionary with all data from the MAGICC output files in
        DataFrames
    parameters (dict): Parameters used in the MAGICC run. Only returned when
        `return_config` is set to True
    """

    with MAGICC6() as magicc:

        # Write out the `Scenario` as a .SCEN-file.
        write_scen_file(scenario, os.path.join(magicc.run_dir, "SCENARIO.SCEN"))

        year_cfg = {}
        if "startyear" in kwargs:
            year_cfg["startyear"] = kwargs.pop("startyear")
        if "endyear" in kwargs:
            year_cfg["endyear"] = kwargs.pop("endyear")
            magicc.set_years(**year_cfg)
        kwargs.setdefault("file_emissionscenario", "SCENARIO.SCEN")
        kwargs.setdefault("rundate", _get_date_time_string())
        magicc.set_config(**kwargs)

        results = magicc.run()

        if return_config:
            return results, magicc.config
        else:
            return results
