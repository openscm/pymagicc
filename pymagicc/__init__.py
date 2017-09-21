# Copyright (c) 2017 pymagicc authors:
#   Robert Gieseke <robert.gieseke@pik-potsdam.de>
# Free software under GNU Affero General Public License v3, see LICENSE
#
# The compiled MAGICC binary (http://www.magicc.org/download6) by Tom Wigley,
# Sarah Raper, and Malte Meinshausen included in this package is licensed under
# a Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported
# License (https://creativecommons.org/licenses/by-nc-sa/3.0/)


# -*- coding: utf-8 -*-

import datetime
import linecache
import logging
import os
import platform
import shutil
import subprocess
import tempfile

from distutils import dir_util

import f90nml
import pandas as pd

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions


_WINDOWS = platform.system() == "Windows"

_magiccpath = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "MAGICC6/MAGICC6_4Download"
)

if not _WINDOWS:
    wine_installed = subprocess.call("type wine", shell=True,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE) == 0
    if not wine_installed:
        logging.warning("Wine is not installed")


# MAGICC's scenario files encode the used regions as follows.
region_codes = {
    11: ['WORLD'],
    20: ['WORLD', "OECD90", "REF", "ASIA", "ALM"],
    21: ['WORLD', "OECD90", "REF", "ASIA", "ALM"],
    31: ['WORLD', "R5OECD", "R5REF", "R5ASIA", "R5MAF", "R5LAM"],
    41: ['WORLD', "R5OECD", "R5REF", "R5ASIA", "R5MAF", "R5LAM", "BUNKERS"]
}

# Order of columns to use when writing scenario files.
_columns = [
    u'YEARS', u'FossilCO2', u'OtherCO2', u'CH4', u'N2O', u'SOx', u'CO',
    u'NMVOC', u'NOx', u'BC', u'OC', u'NH3', u'CF4', u'C2F6', u'C6F14',
    u'HFC23', u'HFC32', u'HFC43-10', u'HFC125', u'HFC134a', u'HFC143a',
    u'HFC227ea', u'HFC245fa', u'SF6'
]

# Units to be used for each column.
units = {
    'BC': 'Mt',
    'C2F6': 'kt',
    'C6F14': 'kt',
    'CF4': 'kt',
    'CH4': 'MtCH4',
    'CO': 'MtCO',
    'FossilCO2': 'GtC',
    'HFC125': 'kt',
    'HFC134a': 'kt',
    'HFC143a': 'kt',
    'HFC227ea': 'kt',
    'HFC23': 'kt',
    'HFC245fa': 'kt',
    'HFC32': 'kt',
    'HFC43-10': 'kt',
    'N2O': 'MtN2O-N',
    'NH3': 'MtN',
    'NMVOC': 'Mt',
    'NOx': 'MtN',
    'OC': 'Mt',
    'OtherCO2': 'GtC',
    'SF6': 'kt',
    'SOx': 'MtS',
    'YEARS': 'Yrs'
}


def _get_number_of_datapoints(scen_file):
    """Return number of timeseries datapoints from a .SCEN-file."""
    return int(linecache.getline(scen_file, 1))


def _get_region_code(scen_file):
    """Return region code for a .SCEN-file."""
    return int(linecache.getline(scen_file, 2))


def read_scen_file(scen_file):
    """
    Reads a MAGICC .SCEN file and returns a
    a dictionary of DataFrames or, for World Only scenarios, a DataFrame.
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
            index_col=0
        )
        output[region].name = region

    if region_code == 11:
        return output["WORLD"]
    else:
        return  output

rcp3pd = read_scen_file(os.path.join(_magiccpath, "RCP3PD.SCEN"))
rcp45 = read_scen_file(os.path.join(_magiccpath, "RCP45.SCEN"))
rcp6 = read_scen_file(os.path.join(_magiccpath, "RCP6.SCEN"))
rcp85 = read_scen_file(os.path.join(_magiccpath, "RCP85.SCEN"))

scenarios = {
    "RCP3PD": rcp3pd,
    "RCP45": rcp45,
    "RCP6": rcp6,
    "RCP85": rcp85
}

def _get_date_time_string():
    """Return a timestamp with current date and time."""
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d %H:%M")


def write_scen_file(scenario,
                    path_or_buf=None,
                    description1=None,
                    description2=None,
                    comment=None):
    """
    Write a Dictionary of DataFrames or DataFrame to a MAGICC .SCEN-file.

    Parameters
    ----------
    scenario: DataFrame or Dict of DataFrames
        DataFrame (for scenarios with only the World region) or Dictionary with
        regions.
    path_or_buf:
        Pathname or file-like object to write the scenario to.
    description_1:
        Optional description line.
    description_2:
        Optional second description line.
    comment:
        Optional comment at end of scenario file.

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
        name = os.path.basename(
            path_or_buf.replace(".SCEN", "")
        )
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
                    data.append(with_digits.format(
                        scenario[region].loc[year][column])
                    )
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


def run(scenario, output_dir=None,
        file_tuningmodel="C4MIP_DEFAULT",
        file_tuningmodel_2="FULLTUNE_DEFAULT",
        return_config=False,
        **kwargs
        ):
    """
    Return output data and (optionally) used parameters from a MAGICC run.

    Parameters
    ----------
    output_dir:
        Path for MAGICC data and binary, if None a temp file which will be
        deleted automatically.
    file_tuningmodel:
        Default Tuningmodel configuration.
    file_tuningmodel_2:
        Default Tuningmodel 2 configuration.
    return_config:
        Additionaly return the full list of parameters used. default False
    kwargs:
        Parameters overwriting default parameters.

    Returns
    -------
    output: dict
        Dictionary with all data from MAGICC output files.
    parameters: dict
        Parameters used in the MAGICC run. Only returned when
        ``return_config`` is set to True
    """

    # Create a temporary directory.
    if output_dir:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        tempdir = output_dir
    else:
        tempdir = tempfile.mkdtemp(prefix="pymagicc-")

    dir_util.copy_tree(_magiccpath, tempdir)

    # Write out the `Scenario` as a .SCEN-file.
    write_scen_file(scenario, os.path.join(tempdir, "SCENARIO.SCEN"))

    # Generate MAGICC simple config.
    magtune_simple_cfg = os.path.join(_magiccpath, "MAGTUNE_SIMPLE.CFG")
    magtune_simple = f90nml.read(magtune_simple_cfg)

    # Update user config.
    magtune_simple['nml_allcfgs']["file_emissionscenario"] = "SCENARIO.SCEN"
    magtune_simple['nml_allcfgs']["file_tuningmodel"] = file_tuningmodel
    magtune_simple['nml_allcfgs']["file_tuningmodel_2"] = file_tuningmodel_2
    magtune_simple['nml_allcfgs']["rundate"] = _get_date_time_string()

    for key, value in kwargs.items():
        magtune_simple['nml_allcfgs'][key] = value

    # Write simple config.
    outpath = os.path.join(tempdir, "MAGTUNE_SIMPLE.CFG")
    f90nml.write(magtune_simple, outpath, force=True)

    command = ['magicc6.exe']

    if not _WINDOWS:
        command.insert(0, 'wine')

    subprocess.check_call(command, cwd=tempdir)

    results = {}

    outfiles = [f for f in os.listdir(tempdir)
                if f.startswith("DAT_") and f.endswith(".OUT")]

    for filename in outfiles:
        name = filename.replace("DAT_", "").replace(".OUT", "")
        results[name] = pd.read_csv(
            os.path.join(tempdir, filename),
            delim_whitespace=True,
            skiprows=19,
            index_col=0
        )

    with open(os.path.join(tempdir, 'PARAMETERS.OUT')) as nml_file:
        parameters = f90nml.read(nml_file)
        parameters = dict(parameters["nml_allcfgs"])
        for k, v in parameters.items():
            if isinstance(v, str):
                parameters[k] = v.strip()
            elif isinstance(v, list):
                if isinstance(v[0], str):
                    parameters[k] = [i.strip().replace("\n", "") for i in v]

    if not output_dir:
        shutil.rmtree(tempdir)

    if return_config:
        return results, parameters
    else:
        return results
