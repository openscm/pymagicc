from os.path import exists

from pymagicc.definitions import (
    DATTYPE_REGIONMODE_REGIONS,
    convert_magicc6_to_magicc7_variables,
    convert_magicc7_to_openscm_variables,
    convert_magicc_to_openscm_regions,
)

DATTYPE_FLAG = "THISFILE_DATTYPE"
"""str: Flag used to indicate the file's data type in MAGICCC"""

REGIONMODE_FLAG = "THISFILE_REGIONMODE"
"""str: Flag used to indicate the file's region mode in MAGICCC"""


def _get_dattype_regionmode_regions_row(regions, scen7=False):
    regions_unique = set(
        [convert_magicc_to_openscm_regions(r, inverse=True) for r in set(regions)]
    )

    def find_region(x):
        return set(x) == regions_unique

    region_rows = DATTYPE_REGIONMODE_REGIONS["regions"].apply(find_region)

    scen7_rows = DATTYPE_REGIONMODE_REGIONS["thisfile_dattype"] == "SCEN7"
    dattype_rows = scen7_rows if scen7 else ~scen7_rows

    region_dattype_row = region_rows & dattype_rows
    if sum(region_dattype_row) != 1:
        error_msg = (
            "Unrecognised regions, they must be part of "
            "pymagicc.definitions.DATTYPE_REGIONMODE_REGIONS. If that doesn't make "
            "sense, please raise an issue at "
            "https://github.com/openscm/pymagicc/issues"
        )
        raise ValueError(error_msg)

    return region_dattype_row


def get_region_order(regions, scen7=False):
    """
    Get the region order expected by MAGICC.

    Parameters
    ----------
    regions : list_like
        The regions to get THISFILE_DATTYPE and THISFILE_REGIONMODE flags for.

    scen7 : bool, optional
        Whether the file we are getting the flags for is a SCEN7 file or not.

    Returns
    -------
    list
        Region order expected by MAGICC for the given region set.
    """
    region_dattype_row = _get_dattype_regionmode_regions_row(regions, scen7=scen7)
    region_order = DATTYPE_REGIONMODE_REGIONS["regions"][region_dattype_row].iloc[0]

    return region_order


def get_dattype_regionmode(regions, scen7=False):
    """
    Get the THISFILE_DATTYPE and THISFILE_REGIONMODE flags for a given region set.

    In all MAGICC input files, there are two flags: THISFILE_DATTYPE and
    THISFILE_REGIONMODE. These tell MAGICC how to read in a given input file. This
    function maps the regions which are in a given file to the value of these flags
    expected by MAGICC.

    Parameters
    ----------
    regions : list_like
        The regions to get THISFILE_DATTYPE and THISFILE_REGIONMODE flags for.

    scen7 : bool, optional
        Whether the file we are getting the flags for is a SCEN7 file or not.

    Returns
    -------
    dict
        Dictionary where the flags are the keys and the values are the value they
        should be set to for the given inputs.
    """
    region_dattype_row = _get_dattype_regionmode_regions_row(regions, scen7=scen7)

    dattype = DATTYPE_REGIONMODE_REGIONS[DATTYPE_FLAG.lower()][region_dattype_row].iloc[
        0
    ]
    regionmode = DATTYPE_REGIONMODE_REGIONS[REGIONMODE_FLAG.lower()][
        region_dattype_row
    ].iloc[0]

    return {DATTYPE_FLAG: dattype, REGIONMODE_FLAG: regionmode}


def _get_openscm_var_from_filepath(filepath):
    """
    Determine the OpenSCM variable from a filepath.

    Uses MAGICC's internal, implicit, filenaming conventions.

    Parameters
    ----------
    filepath : str
        Filepath from which to determine the OpenSCM variable.

    Returns
    -------
    str
        The OpenSCM variable implied by the filepath.
    """
    from pymagicc.io import determine_tool

    reader = determine_tool(filepath, "reader")(filepath)
    openscm_var = convert_magicc7_to_openscm_variables(
        convert_magicc6_to_magicc7_variables(reader._get_variable_from_filepath())
    )

    return openscm_var


def _check_file_exists(file_to_read):
    if not exists(file_to_read):
        raise FileNotFoundError("Cannot find {}".format(file_to_read))


def _strip_emis_variables(in_vars):
    return [v.replace("T_EMIS", "").replace("_EMIS", "") for v in in_vars]
