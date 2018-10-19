import pytest

from pymagicc.definitions import convert_magicc6_to_magicc7_variables, convert_magicc7_to_openscm_variables

@pytest.mark.parametrize("magicc6, magicc7",[("HFC-245ca", "HFC245FA"), ("HFC245ca", "HFC245FA"), ("HFC245ca", "HFC245FA"), ("HFC245ca", "HFC245FA"), ("HFC245ca", "HFC245FA"), ("HFC245ca", "HFC245FA")])
def test_convert_magicc6_to_magicc7_variables(magicc6, magicc7):
    assert convert_magicc6_to_magicc7_variables(magicc6) == magicc7

@pytest.mark.parametrize("magicc7, openscm",[("HFC245FA_EMIS", "Emissions|HFC245fa"), ("CO2I_EMIS", "Emissions|CO2|MAGICC Fossil and Industrial"), ("CH4_EMIS", "Emissions|CH4"),])
def test_convert_magicc7_to_openscm_variables(magicc7, openscm):
    assert convert_magicc7_to_openscm_variables(magicc7) == openscm
