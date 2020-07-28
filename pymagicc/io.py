import re
import warnings
from copy import deepcopy
from datetime import datetime
from numbers import Number
from os.path import basename, exists
from shutil import copyfileobj

import f90nml
import numpy as np
import pandas as pd
from f90nml.namelist import Namelist
from scmdata import ScmDataFrame
from six import StringIO

from .definitions import (
    DATA_HIERARCHY_SEPARATOR,
    DATTYPE_REGIONMODE_REGIONS,
    PART_OF_PRNFILE,
    PART_OF_SCENFILE_WITH_EMISSIONS_CODE_0,
    PART_OF_SCENFILE_WITH_EMISSIONS_CODE_1,
    convert_magicc6_to_magicc7_variables,
    convert_magicc7_to_openscm_variables,
    convert_magicc_to_openscm_regions,
    convert_pint_to_fortran_safe_units,
)
from .magicc_time import (
    _adjust_df_index_to_match_timeseries_type,
    convert_to_datetime,
    convert_to_decimal_year,
)
from .utils import apply_string_substitutions
















def get_generic_rcp_name(inname):
    """
    Convert an RCP name into the generic Pymagicc RCP name

    The conversion is case insensitive.

    Parameters
    ----------
    inname : str
        The name for which to get the generic Pymagicc RCP name

    Returns
    -------
    str
        The generic Pymagicc RCP name

    Examples
    --------
    >>> get_generic_rcp_name("RCP3PD")
    "rcp26"
    """
    # TODO: move into OpenSCM
    mapping = {
        "rcp26": "rcp26",
        "rcp3pd": "rcp26",
        "rcp45": "rcp45",
        "rcp6": "rcp60",
        "rcp60": "rcp60",
        "rcp85": "rcp85",
    }
    try:
        return mapping[inname.lower()]
    except KeyError:
        error_msg = "No generic name for input: {}".format(inname)
        raise ValueError(error_msg)







