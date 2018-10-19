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
        ("Halon1211", "HALON1211"),
    ],
)
def test_convert_magicc6_to_magicc7_variables(magicc6, magicc7):
    assert convert_magicc6_to_magicc7_variables(magicc6) == magicc7


@pytest.mark.parametrize("magicc6", [("HFC-245ca"), ("HFC245ca")])
def test_convert_magicc6_to_magicc7_variables_hfc245ca_error(magicc6):
    error_msg = re.escape(
        "HFC245ca wasn't meant to be included in MAGICC6. Renaming to HFC245fa."
    )
    with pytest.warns(UserWarning, match=error_msg):
        convert_magicc6_to_magicc7_variables(magicc6)


@pytest.mark.parametrize(
    "magicc7, openscm",
    [
        ("HFC245FA_EMIS", "Emissions|HFC245fa"),
        ("CO2I_EMIS", "Emissions|CO2|MAGICC Fossil and Industrial"),
        ("CH4_EMIS", "Emissions|CH4"),
    ],
)
def test_convert_magicc7_to_openscm_variables(magicc7, openscm):
    assert convert_magicc7_to_openscm_variables(magicc7) == openscm
