"""
This module contains all of the relevant definitions for handling MAGICC data.

When we store the data in csv's, we use `Data Packages <https://frictionlessdata.io/
docs/creating-tabular-data-packages-in-python/>`_. These store the data in an easy to
read csv file whilst providing comprehensive metadata describing the data (column
meanings and expected types) in the accompanying ``datapackage.json`` file. Please see
this metadata for further details.

For more details about how these constants are used, see the documentation of
``pymagicc.io``. In particular, the documentation of
``pymagicc.io.get_special_scen_code``, ``pymagicc.io.get_dattype_regionmode`` and
``pymagicc.io.get_region_order`` in :ref:`pymagicc.io`.
"""
from pathlib import Path
import warnings
import functools

import pandas as pd
from pandas_datapackage_reader import read_datapackage


from pymagicc.utils import apply_string_substitutions

DATA_HIERARCHY_SEPARATOR = "|"
"""str: String used to define different levels in our data hierarchies.

For example, "Emissions|CO2|Energy|Coal".

We copy this straight from pyam_ to maintain easy compatibility.
"""

path = Path(__file__).parent


_dtrm = read_datapackage(path, "magicc_dattype_regionmode_regions")

_region_cols = _dtrm.columns.to_series().apply(lambda x: x.startswith("region"))

DATTYPE_REGIONMODE_REGIONS = _dtrm.loc[:, ~_region_cols].copy()
""":obj:`pandas.DataFrame` Mapping between regions and whether a file is SCEN7 or not and the expected values of THISFILE_DATTYPE and THISFILE_REGIONMODE flags in MAGICC.
"""

DATTYPE_REGIONMODE_REGIONS["regions"] = [
    [r for r in raw if not pd.isnull(r)]
    for raw in _dtrm.loc[:, _region_cols].values.tolist()
]

MAGICC7_EMISSIONS_UNITS = read_datapackage(path, "magicc_emisssions_units")
""":obj:`pandas.DataFrame` Definitions of emissions variables and their expected units in MAGICC7.
"""

PART_OF_SCENFILE_WITH_EMISSIONS_CODE_0 = MAGICC7_EMISSIONS_UNITS[
    MAGICC7_EMISSIONS_UNITS["part_of_scenfile_with_emissions_code_0"]
]["magicc_variable"].tolist()
"""list: The emissions which are included in a SCEN file if the SCEN emms code is 0.

See documentation of ``pymagicc.io.get_special_scen_code`` for more details.
"""

PART_OF_SCENFILE_WITH_EMISSIONS_CODE_1 = MAGICC7_EMISSIONS_UNITS[
    MAGICC7_EMISSIONS_UNITS["part_of_scenfile_with_emissions_code_1"]
]["magicc_variable"].tolist()
"""list: The emissions which are included in a SCEN file if the SCEN emms code is 1.

See documentation of ``pymagicc.io.get_special_scen_code`` for more details.
"""

PART_OF_PRNFILE = MAGICC7_EMISSIONS_UNITS[MAGICC7_EMISSIONS_UNITS["part_of_prnfile"]][
    "magicc_variable"
].tolist()
"""list: The emissions which are included in a ``.prn`` file.
"""

MAGICC7_CONCENTRATIONS_UNITS = read_datapackage(path, "magicc_concentrations_units")
""":obj:`pandas.DataFrame` Definitions of concentrations variables and their expected units in MAGICC7.
"""


def get_magicc_region_to_openscm_region_mapping(inverse=False):
    """Get the mappings from MAGICC to OpenSCM regions.

    This is not a pure inverse of the other way around. For example, we never provide
    "GLOBAL" as a MAGICC return value because it's unnecesarily confusing when we also
    have "World". Fortunately MAGICC doesn't ever read the name "GLOBAL" so this
    shouldn't matter.

    Parameters
    ----------
    inverse : bool
        If True, return the inverse mappings i.e. MAGICC to OpenSCM mappings
    Returns
    -------
    dict
        Dictionary of mappings
    """

    def get_openscm_replacement(in_region):
        world = "World"
        if in_region in ("WORLD", "GLOBAL"):
            return world
        if in_region in ("BUNKERS"):
            return DATA_HIERARCHY_SEPARATOR.join([world, "Bunkers"])
        elif in_region.startswith(("NH", "SH")):
            in_region = in_region.replace("-", "")
            hem = "Northern Hemisphere" if "NH" in in_region else "Southern Hemisphere"
            if in_region in ("NH", "SH"):
                return DATA_HIERARCHY_SEPARATOR.join([world, hem])

            land_ocean = "Land" if "LAND" in in_region else "Ocean"
            return DATA_HIERARCHY_SEPARATOR.join([world, hem, land_ocean])
        else:
            return DATA_HIERARCHY_SEPARATOR.join([world, in_region])

    # we generate the mapping dynamically, the first name in the list
    # is the one which will be used for inverse mappings
    _magicc_regions = [
        "WORLD",
        "GLOBAL",
        "OECD90",
        "ALM",
        "REF",
        "ASIA",
        "R5ASIA",
        "R5OECD",
        "R5REF",
        "R5MAF",
        "R5LAM",
        "R6OECD90",
        "R6REF",
        "R6LAM",
        "R6MAF",
        "R6ASIA",
        "NHOCEAN",
        "SHOCEAN",
        "NHLAND",
        "SHLAND",
        "NH-OCEAN",
        "SH-OCEAN",
        "NH-LAND",
        "SH-LAND",
        "SH",
        "NH",
        "BUNKERS",
    ]

    replacements = {}
    for magicc_region in _magicc_regions:
        openscm_region = get_openscm_replacement(magicc_region)
        # i.e. if we've already got a value for the inverse, we don't want to overwrite
        if (openscm_region in replacements.values()) and inverse:
            continue
        replacements[magicc_region] = openscm_region

    if inverse:
        return {v: k for k, v in replacements.items()}
    else:
        return replacements


MAGICC_REGION_TO_OPENSCM_REGION_MAPPING = get_magicc_region_to_openscm_region_mapping()
"""dict: Mappings from MAGICC regions to OpenSCM regions"""

OPENSCM_REGION_TO_MAGICC_REGION_MAPPING = get_magicc_region_to_openscm_region_mapping(
    inverse=True
)
"""dict: Mappings from OpenSCM regions to MAGICC regions
"""


@functools.lru_cache(None)
def _apply_convert_magicc_to_openscm_regions(regions, inverse):
    if inverse:
        return apply_string_substitutions(
            regions,
            OPENSCM_REGION_TO_MAGICC_REGION_MAPPING,
            unused_substitutions="ignore",  # TODO: make this warn and see what happens
        )
    else:
        return apply_string_substitutions(
            regions,
            MAGICC_REGION_TO_OPENSCM_REGION_MAPPING,
            unused_substitutions="ignore",  # TODO: make this warn and see what happens
            case_insensitive=True,  # MAGICC regions are case insensitive
        )


def convert_magicc_to_openscm_regions(regions, inverse=False):
    """
    Convert MAGICC regions to OpenSCM regions

    Parameters
    ----------
    regions : list_like, str
        Regions to convert

    inverse : bool
        If True, convert the other way i.e. convert OpenSCM regions to MAGICC7
        regions

    Returns
    -------
    ``type(regions)``
        Set of converted regions
    """
    if isinstance(regions, (list, pd.Index)):
        return [_apply_convert_magicc_to_openscm_regions(r, inverse) for r in regions]
    else:
        return _apply_convert_magicc_to_openscm_regions(regions, inverse)


def get_magicc7_to_openscm_variable_mapping(inverse=False):
    """Get the mappings from MAGICC7 to OpenSCM variables.

    Parameters
    ----------
    inverse : bool
        If True, return the inverse mappings i.e. OpenSCM to MAGICC7 mappings

    Returns
    -------
    dict
        Dictionary of mappings
    """

    def get_openscm_replacement(in_var):
        if in_var.endswith("_INVERSE_EMIS"):
            prefix = "Inverse Emissions"
        elif in_var.endswith("_EMIS"):
            prefix = "Emissions"
        elif in_var.endswith("_CONC"):
            prefix = "Atmospheric Concentrations"
        elif in_var.endswith("_RF"):
            prefix = "Radiative Forcing"
        elif in_var.endswith("_OT"):
            prefix = "Optical Thickness"
        else:
            raise ValueError("This shouldn't happen")

        variable = in_var.split("_")[0]
        # I hate edge cases
        if variable.endswith("EQ"):
            variable = variable.replace("EQ", " Equivalent")

        if "GHG" in variable:
            variable = variable.replace("GHG", "Greenhouse Gases")

        if "BIOMASSAER" in variable:
            variable = variable.replace("BIOMASSAER", "Aerosols|MAGICC AFOLU")

        if "CO2CH4N2O" in variable:
            variable = variable.replace("CO2CH4N2O", "CO2, CH4 and N2O")

        aggregate_indicators = {
            "KYOTO": "Kyoto Gases",
            "FGASSUM": "F Gases",
            "MHALOSUM": "Montreal Protocol Halogen Gases",
        }
        for agg_indicator, long_name in aggregate_indicators.items():
            if variable.startswith(agg_indicator):
                stripped_var = variable.replace(agg_indicator, "")
                if stripped_var:
                    variable = DATA_HIERARCHY_SEPARATOR.join([stripped_var, long_name])
                else:
                    variable = long_name

        edge_case_B = variable.upper() in ("HCFC141B", "HCFC142B")
        if variable.endswith("I"):
            variable = DATA_HIERARCHY_SEPARATOR.join(
                [variable[:-1], "MAGICC Fossil and Industrial"]
            )
        elif variable.endswith("B") and not edge_case_B:
            variable = DATA_HIERARCHY_SEPARATOR.join([variable[:-1], "MAGICC AFOLU"])

        case_adjustments = {
            "SOX": "SOx",
            "NOX": "NOx",
            "HFC134A": "HFC134a",
            "HFC143A": "HFC143a",
            "HFC152A": "HFC152a",
            "HFC227EA": "HFC227ea",
            "HFC236FA": "HFC236fa",
            "HFC245FA": "HFC245fa",
            "HFC365MFC": "HFC365mfc",
            "HCFC141B": "HCFC141b",
            "HCFC142B": "HCFC142b",
            "CH3CCL3": "CH3CCl3",
            "CCL4": "CCl4",
            "CH3CL": "CH3Cl",
            "CH2CL2": "CH2Cl2",
            "CHCL3": "CHCl3",
            "CH3BR": "CH3Br",
            "HALON1211": "Halon1211",
            "HALON1301": "Halon1301",
            "HALON2402": "Halon2402",
            "HALON1202": "Halon1202",
            "SOLAR": "Solar",
            "VOLCANIC": "Volcanic",
            "EXTRA": "Extra",
        }
        variable = apply_string_substitutions(variable, case_adjustments)

        return DATA_HIERARCHY_SEPARATOR.join([prefix, variable])

    magicc7_suffixes = ["_EMIS", "_CONC", "_RF", "_OT", "_INVERSE_EMIS"]
    magicc7_base_vars = MAGICC7_EMISSIONS_UNITS.magicc_variable.tolist() + [
        "SOLAR",
        "VOLCANIC",
        "CO2EQ",
        "KYOTOCO2EQ",
        "FGASSUMHFC134AEQ",
        "MHALOSUMCFC12EQ",
        "GHG",
        "KYOTOGHG",
        "FGASSUM",
        "MHALOSUM",
        "BIOMASSAER",
        "CO2CH4N2O",
        "EXTRA",
    ]
    magicc7_vars = [
        base_var + suffix
        for base_var in magicc7_base_vars
        for suffix in magicc7_suffixes
    ]

    replacements = {m7v: get_openscm_replacement(m7v) for m7v in magicc7_vars}

    replacements.update(
        {
            "SURFACE_TEMP": "Surface Temperature",
            "TOTAL_INCLVOLCANIC_RF": "Radiative Forcing",
            "VOLCANIC_ANNUAL_RF": "Radiative Forcing|Volcanic",
            "TOTAL_ANTHRO_RF": "Radiative Forcing|Anthropogenic",
            "TOTAER_DIR_RF": "Radiative Forcing|Aerosols|Direct Effect",
            "CLOUD_TOT_RF": "Radiative Forcing|Aerosols|Indirect Effect",
            "MINERALDUST_RF": "Radiative Forcing|Mineral Dust",
            "STRATOZ_RF": "Radiative Forcing|Stratospheric Ozone",
            "TROPOZ_RF": "Radiative Forcing|Tropospheric Ozone",
            "CH4OXSTRATH2O_RF": "Radiative Forcing|CH4 Oxidation Stratospheric H2O",  # what is this
            "LANDUSE_RF": "Radiative Forcing|Land-use Change",
            "BCSNOW_RF": "Radiative Forcing|Black Carbon on Snow",
            "CO2PF_EMIS": "Land to Air Flux|CO2|MAGICC Permafrost",
            # "CH4PF_EMIS": "Land to Air Flux|CH4|MAGICC Permafrost",  # TODO: test and then add when needed
        }
    )

    agg_ocean_heat_top = "Aggregated Ocean Heat Content"
    heat_content_aggreg_depths = {
        "HEATCONTENT_AGGREG_DEPTH{}".format(i): "{}{}Depth {}".format(
            agg_ocean_heat_top, DATA_HIERARCHY_SEPARATOR, i
        )
        for i in range(1, 4)
    }
    replacements.update(heat_content_aggreg_depths)
    replacements.update({"HEATCONTENT_AGGREG_TOTAL": agg_ocean_heat_top})

    ocean_temp_layer = {
        "OCEAN_TEMP_LAYER_{0:03d}".format(i): "Ocean Temperature{}Layer {}".format(
            DATA_HIERARCHY_SEPARATOR, i
        )
        for i in range(1, 999)
    }
    replacements.update(ocean_temp_layer)

    if inverse:
        return {v: k for k, v in replacements.items()}
    else:
        return replacements


MAGICC7_TO_OPENSCM_VARIABLES_MAPPING = get_magicc7_to_openscm_variable_mapping()
"""dict: Mappings from MAGICC7 variables to OpenSCM variables
"""

OPENSCM_TO_MAGICC7_VARIABLES_MAPPING = get_magicc7_to_openscm_variable_mapping(
    inverse=True
)
"""dict: Mappings from OpenSCM variables to MAGICC7 variables
"""


@functools.lru_cache(None)
def _apply_convert_magicc7_to_openscm_variables(v, inverse):
    if inverse:
        return apply_string_substitutions(
            v,
            OPENSCM_TO_MAGICC7_VARIABLES_MAPPING,
            unused_substitutions="ignore",  # TODO: make this warn and see what happens
        )
    else:
        return apply_string_substitutions(
            v,
            MAGICC7_TO_OPENSCM_VARIABLES_MAPPING,
            unused_substitutions="ignore",  # TODO: make this warn and see what happens
            case_insensitive=True,  # MAGICC variables are case insensitive
        )


def convert_magicc7_to_openscm_variables(variables, inverse=False):
    """
    Convert MAGICC7 variables to OpenSCM variables

    Parameters
    ----------
    variables : list_like, str
        Variables to convert

    inverse : bool
        If True, convert the other way i.e. convert OpenSCM variables to MAGICC7
        variables

    Returns
    -------
    ``type(variables)``
        Set of converted variables
    """
    if isinstance(variables, (list, pd.Index)):
        return [
            _apply_convert_magicc7_to_openscm_variables(v, inverse) for v in variables
        ]
    else:
        return _apply_convert_magicc7_to_openscm_variables(variables, inverse)


def get_magicc6_to_magicc7_variable_mapping(inverse=False):
    """Get the mappings from MAGICC6 to MAGICC7 variables.

    Note that this mapping is not one to one. For example, "HFC4310", "HFC43-10" and
    "HFC-43-10" in MAGICC6 both map to "HFC4310" in MAGICC7 but "HFC4310" in
    MAGICC7 maps back to "HFC4310".

    Note that HFC-245fa was mistakenly labelled as HFC-245ca in MAGICC6. In reality,
    they are not the same thing. However, the MAGICC6 labelling was merely a typo so
    the mapping between the two is one-to-one.

    Parameters
    ----------
    inverse : bool
        If True, return the inverse mappings i.e. MAGICC7 to MAGICC6 mappings

    Returns
    -------
    dict
        Dictionary of mappings
    """
    # we generate the mapping dynamically, the first name in the list
    # is the one which will be used for inverse mappings
    magicc6_simple_mapping_vars = [
        "KYOTO-CO2EQ",
        "CO2I",
        "CO2B",
        "CH4",
        "N2O",
        "BC",
        "OC",
        "SOx",
        "NOx",
        "NMVOC",
        "CO",
        "SF6",
        "NH3",
        "CF4",
        "C2F6",
        "HFC4310",
        "HFC43-10",
        "HFC-43-10",
        "HFC4310",
        "HFC134a",
        "HFC143a",
        "HFC227ea",
        "CCl4",
        "CH3CCl3",
        "HFC245fa",
        "Halon 1211",
        "Halon 1202",
        "Halon 1301",
        "Halon 2402",
        "Halon1211",
        "Halon1202",
        "Halon1301",
        "Halon2402",
        "CH3Br",
        "CH3Cl",
        "C6F14",
    ]

    magicc6_sometimes_hyphen_vars = [
        "CFC-11",
        "CFC-12",
        "CFC-113",
        "CFC-114",
        "CFC-115",
        "HCFC-22",
        "HFC-23",
        "HFC-32",
        "HFC-125",
        "HFC-134a",
        "HFC-143a",
        "HCFC-141b",
        "HCFC-142b",
        "HFC-227ea",
        "HFC-245fa",
    ]
    magicc6_sometimes_hyphen_vars = [
        v.replace("-", "") for v in magicc6_sometimes_hyphen_vars
    ] + magicc6_sometimes_hyphen_vars

    magicc6_sometimes_underscore_vars = [
        "HFC43_10",
        "CFC_11",
        "CFC_12",
        "CFC_113",
        "CFC_114",
        "CFC_115",
        "HCFC_22",
        "HCFC_141b",
        "HCFC_142b",
    ]
    magicc6_sometimes_underscore_replacements = {
        v: v.replace("_", "") for v in magicc6_sometimes_underscore_vars
    }

    special_case_replacements = {
        "FossilCO2": "CO2I",
        "OtherCO2": "CO2B",
        "MCF": "CH3CCL3",
        "CARB_TET": "CCL4",
        "MHALOSUMCFC12EQ": "MHALOSUMCFC12EQ",  # special case to avoid confusion with MCF
    }

    one_way_replacements = {"HFC-245ca": "HFC245FA", "HFC245ca": "HFC245FA"}

    all_possible_magicc6_vars = (
        magicc6_simple_mapping_vars
        + magicc6_sometimes_hyphen_vars
        + magicc6_sometimes_underscore_vars
        + list(special_case_replacements.keys())
        + list(one_way_replacements.keys())
    )
    replacements = {}
    for m6v in all_possible_magicc6_vars:
        if m6v in special_case_replacements:
            replacements[m6v] = special_case_replacements[m6v]
        elif (
            m6v in magicc6_sometimes_underscore_vars and not inverse
        ):  # underscores one way
            replacements[m6v] = magicc6_sometimes_underscore_replacements[m6v]
        elif (m6v in one_way_replacements) and not inverse:
            replacements[m6v] = one_way_replacements[m6v]
        else:
            m7v = m6v.replace("-", "").replace(" ", "").upper()
            # i.e. if we've already got a value for the inverse, we don't
            # want to overwrite it
            if (m7v in replacements.values()) and inverse:
                continue
            replacements[m6v] = m7v

    if inverse:
        return {v: k for k, v in replacements.items()}
    else:
        return replacements


MAGICC6_TO_MAGICC7_VARIABLES_MAPPING = get_magicc6_to_magicc7_variable_mapping()
"""dict: Mappings from MAGICC6 variables to MAGICC7 variables
"""

MAGICC7_TO_MAGICC6_VARIABLES_MAPPING = get_magicc6_to_magicc7_variable_mapping(
    inverse=True
)
"""dict: Mappings from MAGICC7 variables to MAGICC6 variables
"""


@functools.lru_cache(None)
def _apply_convert_magicc6_to_magicc7_variables(variables, inverse):
    def hfc245ca_included(variables):
        variables = [variables] if isinstance(variables, str) else variables
        return any([v.replace("-", "").lower() == "hfc245ca" for v in variables])

    if hfc245ca_included(variables):
        error_msg = (
            "HFC245ca wasn't meant to be included in MAGICC6. Renaming to HFC245fa."
        )
        warnings.warn(error_msg)

    if inverse:
        return apply_string_substitutions(
            variables,
            MAGICC7_TO_MAGICC6_VARIABLES_MAPPING,
            unused_substitutions="ignore",  # TODO: make this warn and see what happens
            case_insensitive=True,  # MAGICC variables are case insensitive
        )
    else:
        return apply_string_substitutions(
            variables,
            MAGICC6_TO_MAGICC7_VARIABLES_MAPPING,
            unused_substitutions="ignore",  # TODO: make this warn and see what happens
            case_insensitive=True,  # MAGICC variables are case insensitive
        )


def convert_magicc6_to_magicc7_variables(variables, inverse=False):
    """
    Convert MAGICC6 variables to MAGICC7 variables

    Parameters
    ----------
    variables : list_like, str
        Variables to convert

    inverse : bool
        If True, convert the other way i.e. convert MAGICC7 variables to MAGICC6
        variables

    Raises
    ------
    ValueError
        If you try to convert HFC245ca, or some variant thereof, you will get a
        ValueError. The reason is that this variable was never meant to be included in
        MAGICC6, it was just an accident. See, for example, the text in the
        description section of ``pymagicc/MAGICC6/run/HISTRCP_HFC245fa_CONC.IN``:
        "...HFC245fa, rather than HFC245ca, is the actually used isomer.".

    Returns
    -------
    ``type(variables)``
        Set of converted variables
    """
    if isinstance(variables, (list, pd.Index)):
        return [
            _apply_convert_magicc6_to_magicc7_variables(v, inverse) for v in variables
        ]
    else:
        return _apply_convert_magicc6_to_magicc7_variables(variables, inverse)


def get_pint_to_fortran_safe_units_mapping(inverse=False):
    """Get the mappings from Pint to Fortran safe units.

    Fortran can't handle special characters like "^" or "/" in names, but we need
    these in Pint. Conversely, Pint stores variables with spaces by default e.g. "Mt
    CO2 / yr" but we don't want these in the input files as Fortran is likely to think
    the whitespace is a delimiter.

    Parameters
    ----------
    inverse : bool
        If True, return the inverse mappings i.e. Fortran safe to Pint mappings

    Returns
    -------
    dict
        Dictionary of mappings
    """
    replacements = {"^": "super", "/": "per", " ": ""}
    if inverse:
        replacements = {v: k for k, v in replacements.items()}
        # mapping nothing to something is obviously not going to work in the inverse
        # hence remove
        replacements.pop("")

    return replacements


PINT_TO_FORTRAN_SAFE_UNITS_MAPPING = get_pint_to_fortran_safe_units_mapping()
"""dict: mappings required to make Pint units Fortran safe.
"""

FORTRAN_SAFE_TO_PINT_UNITS_MAPPING = get_pint_to_fortran_safe_units_mapping(
    inverse=True
)
"""dict: mappings required to convert our Fortran safe units to Pint.
"""


def convert_pint_to_fortran_safe_units(units, inverse=False):
    """
    Convert Pint units to Fortran safe units

    Parameters
    ----------
    units : list_like, str
        Units to convert

    inverse : bool
        If True, convert the other way i.e. convert Fortran safe units to Pint units

    Returns
    -------
    ``type(units)``
        Set of converted units
    """
    if inverse:
        return apply_string_substitutions(units, FORTRAN_SAFE_TO_PINT_UNITS_MAPPING)
    else:
        return apply_string_substitutions(units, PINT_TO_FORTRAN_SAFE_UNITS_MAPPING)
