import warnings


import pytest
import re


from pymagicc.definitions import (
    convert_magicc6_to_magicc7_variables,
    convert_magicc7_to_openscm_variables,
    convert_magicc_to_openscm_regions,
)


@pytest.mark.parametrize(
    "magicc6, magicc7",
    [
        ("HCFC-141b", "HCFC141B"),
        ("HCFC141b", "HCFC141B"),
        ("HFC4310", "HFC4310"),
        ("HFC43-10", "HFC4310"),
        ("HFC-43-10", "HFC4310"),
        ("OtherCO2", "CO2B"),
        ("FossilCO2", "CO2I"),
        ("SOx", "SOX"),
        ("Halon1211", "HALON1211"),
        ("CARB_TET", "CCL4"),
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
        ("HCFC141B", "HCFC141b"),
        ("HFC23", "HFC23"),
        ("HFC4310", "HFC4310"),
        ("CO2B", "OtherCO2"),
        ("CO2I", "FossilCO2"),
        ("SOX", "SOx"),
        ("HALON1211", "Halon 1211"),
        ("HFC245FA", "HFC245fa"),
        ("CCL4", "CARB_TET"),
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
        ("CH3CCl3_EMIS", "Emissions|CH3CCl3"),
        ("CH3CCL3_EMIS", "Emissions|CH3CCl3"),
        ("CH4_CONC", "Atmospheric Concentrations|CH4"),
        ("EXTRA_RF", "Radiative Forcing|Extra"),
        ("CCL4_INVERSE_EMIS", "Inverse Emissions|CCl4"),
        ("CO2T_EMIS", "Emissions|CO2"),
        ("CH4T_EMIS", "Emissions|CH4"),
        ("N2OT_EMIS", "Emissions|N2O"),
        ("CO2PF_EMIS", "Land to Air Flux|CO2|MAGICC Permafrost"),
        ("CH4PF_EMIS", "Land to Air Flux|CH4|MAGICC Permafrost"),
        ("SURFACE_TEMP", "Surface Temperature"),
        ("SURFACE_TEMP_SUBANNUAL", "Surface Temperature"),
        ("CC4F8_CONC", "Atmospheric Concentrations|cC4F8"),
        ("AIR_CIRRUS_RF", "Radiative Forcing|Aviation|Cirrus"),
        ("AIR_CIRRUS_EFFRF", "Effective Radiative Forcing|Aviation|Cirrus"),
        ("AIR_CONTRAIL_RF", "Radiative Forcing|Aviation|Contrail"),
        ("AIR_CONTRAIL_EFFRF", "Effective Radiative Forcing|Aviation|Contrail"),
        ("AIR_H2O_RF", "Radiative Forcing|Aviation|H2O"),
        ("AIR_H2O_EFFRF", "Effective Radiative Forcing|Aviation|H2O"),
        # ("CH4CLATHRATE_EMIS", "Emissions|CH4|???")
        ("CH4_EFFRF", "Effective Radiative Forcing|CH4"),
        ("GHG_EFFRF", "Effective Radiative Forcing|Greenhouse Gases"),
        ("TOTAL_ANTHRO_EFFRF", "Effective Radiative Forcing|Anthropogenic"),
        ("TOTAER_DIR_EFFRF", "Effective Radiative Forcing|Aerosols|Direct Effect"),
        ("CLOUD_TOT_EFFRF", "Effective Radiative Forcing|Aerosols|Indirect Effect"),
        (
            "CH4OXSTRATH2O_EFFRF",
            "Effective Radiative Forcing|CH4 Oxidation Stratospheric H2O",
        ),
        ("LANDUSE_EFFRF", "Effective Radiative Forcing|Land-use Change"),
        ("STRATOZ_EFFRF", "Effective Radiative Forcing|Stratospheric Ozone"),
        ("TROPOZ_EFFRF", "Effective Radiative Forcing|Tropospheric Ozone"),
        ("KYOTOGHG_EFFRF", "Effective Radiative Forcing|Greenhouse Gases|Kyoto Gases"),
        (
            "AIR_CONTRAILANDCIRRUS_EFFRF",
            "Effective Radiative Forcing|Aviation|Contrail and Cirrus",
        ),
        (
            "BIOMASSAER_EFFRF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|MAGICC AFOLU",
        ),
        (
            "MINERALDUST_EFFRF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|Mineral Dust",
        ),
        (
            "OCI_EFFRF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|OC|MAGICC Fossil and Industrial",
        ),
        (
            "BCI_EFFRF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|BC|MAGICC Fossil and Industrial",
        ),
        (
            "SOXI_EFFRF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|SOx|MAGICC Fossil and Industrial",
        ),
        (
            "NOXI_EFFRF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|NOx|MAGICC Fossil and Industrial",
        ),
        (
            "NH3I_EFFRF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|NH3|MAGICC Fossil and Industrial",
        ),
        ("TOTAL_INCLVOLCANIC_EFFRF", "Effective Radiative Forcing"),
        ("SLR_TOT", "Sea Level Rise"),
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
        ("CH3CCL3_EMIS", "Emissions|CH3CCl3"),
        ("CCL4_INVERSE_EMIS", "Inverse Emissions|CCl4"),
        ("CO2_EMIS", "Emissions|CO2"),
        ("CH4_EMIS", "Emissions|CH4"),
        ("N2O_EMIS", "Emissions|N2O"),
        ("CO2PF_EMIS", "Land to Air Flux|CO2|MAGICC Permafrost"),
        ("SURFACE_TEMP", "Surface Temperature"),
        ("CC4F8_CONC", "Atmospheric Concentrations|cC4F8"),
        ("AIR_CIRRUS_RF", "Radiative Forcing|Aviation|Cirrus"),
        ("AIR_CONTRAIL_RF", "Radiative Forcing|Aviation|Contrail"),
        ("AIR_H2O_RF", "Radiative Forcing|Aviation|H2O"),
        ("CH4_EFFRF", "Effective Radiative Forcing|CH4"),
        ("GHG_EFFRF", "Effective Radiative Forcing|Greenhouse Gases"),
        ("TOTAL_ANTHRO_EFFRF", "Effective Radiative Forcing|Anthropogenic"),
        ("TOTAER_DIR_EFFRF", "Effective Radiative Forcing|Aerosols|Direct Effect"),
        ("CLOUD_TOT_EFFRF", "Effective Radiative Forcing|Aerosols|Indirect Effect"),
        (
            "CH4OXSTRATH2O_EFFRF",
            "Effective Radiative Forcing|CH4 Oxidation Stratospheric H2O",
        ),
        ("LANDUSE_EFFRF", "Effective Radiative Forcing|Land-use Change"),
        ("STRATOZ_EFFRF", "Effective Radiative Forcing|Stratospheric Ozone"),
        ("TROPOZ_EFFRF", "Effective Radiative Forcing|Tropospheric Ozone"),
        ("KYOTOGHG_EFFRF", "Effective Radiative Forcing|Greenhouse Gases|Kyoto Gases"),
        (
            "AIR_CONTRAILANDCIRRUS_EFFRF",
            "Effective Radiative Forcing|Aviation|Contrail and Cirrus",
        ),
        (
            "BIOMASSAER_EFFRF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|MAGICC AFOLU",
        ),
        (
            "MINERALDUST_EFFRF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|Mineral Dust",
        ),
        (
            "OCI_EFFRF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|OC|MAGICC Fossil and Industrial",
        ),
        (
            "BCI_EFFRF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|BC|MAGICC Fossil and Industrial",
        ),
        (
            "SOXI_EFFRF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|SOx|MAGICC Fossil and Industrial",
        ),
        (
            "NOXI_EFFRF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|NOx|MAGICC Fossil and Industrial",
        ),
        (
            "NH3I_EFFRF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|NH3|MAGICC Fossil and Industrial",
        ),
        ("TOTAL_INCLVOLCANIC_EFFRF", "Effective Radiative Forcing"),
        ("SLR_TOT", "Sea Level Rise"),
    ],
)
def test_convert_openscm_to_magicc7_variables(magicc7, openscm):
    assert convert_magicc7_to_openscm_variables(openscm, inverse=True) == magicc7
    # OpenSCM variables are case sensitive hence this should warn
    pytest.xfail("Warnings are turned off")
    msg = "No substitution available for {'" + "{}".format(openscm.upper()) + "'}"
    with warnings.catch_warnings(record=True) as warn_result:
        convert_magicc7_to_openscm_variables(openscm.upper(), inverse=True)

    assert len(warn_result) == 1
    assert str(warn_result[0].message) == msg


@pytest.mark.parametrize(
    "magicc7, openscm",
    [
        ("WORLD", "World"),
        ("OECD90", "World|OECD90"),
        ("ALM", "World|ALM"),
        ("REF", "World|REF"),
        ("ASIA", "World|ASIA"),
        ("R5ASIA", "World|R5ASIA"),
        ("R5OECD", "World|R5OECD"),
        ("R5REF", "World|R5REF"),
        ("R5MAF", "World|R5MAF"),
        ("R5LAM", "World|R5LAM"),
        ("R5.2OECD", "World|R5.2OECD"),
        ("R5.2REF", "World|R5.2REF"),
        ("R5.2LAM", "World|R5.2LAM"),
        ("R5.2MAF", "World|R5.2MAF"),
        ("R5.2ASIA", "World|R5.2ASIA"),
        ("NHOCEAN", "World|Northern Hemisphere|Ocean"),
        ("SHOCEAN", "World|Southern Hemisphere|Ocean"),
        ("NHLAND", "World|Northern Hemisphere|Land"),
        ("SHLAND", "World|Southern Hemisphere|Land"),
        ("NH", "World|Northern Hemisphere"),
        ("SH", "World|Southern Hemisphere"),
        ("BUNKERS", "World|Bunkers"),
        ("N34", "World|El Nino N3.4"),
        ("AMV", "World|North Atlantic Ocean"),
        ("OCEAN", "World|Ocean"),
        ("LAND", "World|Land"),
    ],
)
def test_convert_openscm_to_magicc_regions(magicc7, openscm):
    assert convert_magicc_to_openscm_regions(magicc7, inverse=False) == openscm
    assert convert_magicc_to_openscm_regions(openscm, inverse=True) == magicc7


@pytest.mark.parametrize(
    "magicc7, openscm",
    [
        ("GLOBAL", "World"),
        ("NH-OCEAN", "World|Northern Hemisphere|Ocean"),
        ("SH-OCEAN", "World|Southern Hemisphere|Ocean"),
        ("NH-LAND", "World|Northern Hemisphere|Land"),
        ("SH-LAND", "World|Southern Hemisphere|Land"),
        ("R6OECD90", "World|R5.2OECD"),
        ("R6REF", "World|R5.2REF"),
        ("R6LAM", "World|R5.2LAM"),
        ("R6MAF", "World|R5.2MAF"),
        ("R6ASIA", "World|R5.2ASIA"),
    ],
)
def test_convert_openscm_to_magicc_regions_one_way(magicc7, openscm):
    assert convert_magicc_to_openscm_regions(magicc7, inverse=False) == openscm
