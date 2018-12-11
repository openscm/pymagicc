import warnings


import pytest
import re


from pymagicc.definitions import (
    convert_magicc6_to_magicc7_variables,
    convert_magicc7_to_openscm_variables,
)


@pytest.mark.parametrize(
    "magicc6, magicc7",
    [
        ("HCFC-141b", "HCFC141B"),
        ("HCFC141b", "HCFC141B"),
        ("OtherCO2", "CO2B"),
        ("FossilCO2", "CO2I"),
        ("SOx", "SOX"),
        ("Halon1211", "HALON1211"),
    ],
)
def test_convert_magicc6_to_magicc7_variables(magicc6, magicc7):
    assert convert_magicc6_to_magicc7_variables(magicc6) == magicc7
    assert convert_magicc6_to_magicc7_variables(magicc6.upper()) == magicc7
    assert convert_magicc6_to_magicc7_variables(magicc6.lower()) == magicc7


@pytest.mark.parametrize("magicc6", [("HFC-245ca"), ("HFC245ca")])
def test_convert_magicc6_to_magicc7_variables_hfc245ca_warning(magicc6):
    warning_msg = re.escape(
        "HFC245ca wasn't meant to be included in MAGICC6. Renaming to HFC245fa."
    )
    with pytest.warns(UserWarning, match=warning_msg):
        convert_magicc6_to_magicc7_variables(magicc6)


@pytest.mark.parametrize(
    "magicc7, magicc6",
    [
        ("HCFC141B", "HCFC-141b"),
        ("CO2B", "OtherCO2"),
        ("CO2I", "FossilCO2"),
        ("SOX", "SOx"),
        ("HALON1211", "Halon 1211"),
        ("HFC245FA", "HFC245fa"),
    ],
)
def test_convert_magicc7_to_magicc6_variables(magicc7, magicc6):
    assert convert_magicc6_to_magicc7_variables(magicc7, inverse=True) == magicc6
    assert (
        convert_magicc6_to_magicc7_variables(magicc7.upper(), inverse=True) == magicc6
    )
    assert (
        convert_magicc6_to_magicc7_variables(magicc7.lower(), inverse=True) == magicc6
    )


@pytest.mark.parametrize(
    "magicc7, openscm",
    [
        ("HFC245FA_EMIS", "Emissions|HFC245fa"),
        ("CO2I_EMIS", "Emissions|CO2|MAGICC Fossil and Industrial"),
        ("CH4_EMIS", "Emissions|CH4"),
        ("CH3CCl3_EMIS", "Emissions|CH3CCl3"),
        ("CH3CCL3_EMIS", "Emissions|CH3CCl3"),
    ],
)
def test_convert_magicc7_to_openscm_variables(magicc7, openscm):
    assert convert_magicc7_to_openscm_variables(magicc7) == openscm
    assert convert_magicc7_to_openscm_variables(magicc7.upper()) == openscm
    assert convert_magicc7_to_openscm_variables(magicc7.lower()) == openscm


@pytest.mark.parametrize(
    "magicc7, openscm",
    [
        ("HFC245FA_EMIS", "Emissions|HFC245fa"),
        ("CO2I_EMIS", "Emissions|CO2|MAGICC Fossil and Industrial"),
        ("CH4_EMIS", "Emissions|CH4"),
        ("CH3CCL3_EMIS", "Emissions|CH3CCl3"),
    ],
)
def test_convert_openscm_to_magicc7_variables(magicc7, openscm):
    assert convert_magicc7_to_openscm_variables(openscm, inverse=True) == magicc7
    # OpenSCM variables are case sensitive hence this should not work
    error_msg = re.escape(
        "No conversion available for {'" + "{}".format(openscm.upper()) + "'}"
    )
    with pytest.raises(ValueError, match=error_msg):
        convert_magicc7_to_openscm_variables(openscm.upper(), inverse=True)
