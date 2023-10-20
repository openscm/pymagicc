import re
import warnings

import pytest

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


@pytest.mark.parametrize("suffix", ["RF", "ERF"])
@pytest.mark.parametrize(
    "suffix_part_1",
    [
        "I",
        "B",
        "T",
    ],
)
@pytest.mark.parametrize(
    "variable", ["OC", "BC", "SOX", "NO3", "BIOMASSAER", "MINERALDUST"]
)
def test_dir_aerosols(variable, suffix_part_1, suffix):
    no_prefix_variable = ["BIOMASSAER", "MINERALDUST"]

    if variable in no_prefix_variable:
        # Ignoring the prefix
        openscm_var = convert_magicc7_to_openscm_variables(
            "{}_{}".format(variable, suffix)
        )
    else:
        openscm_var = convert_magicc7_to_openscm_variables(
            "{}{}_{}".format(variable, suffix_part_1, suffix)
        )

    assert "Aerosols|Direct Effect" in openscm_var
    if suffix == "RF":
        assert openscm_var.startswith("Radiative Forcing")
    elif suffix == "ERF":
        assert openscm_var.startswith("Effective Radiative Forcing")

    openscm_var_name = variable if variable != "SOX" else "SOx"
    if variable not in no_prefix_variable:
        if suffix_part_1 == "I":
            assert openscm_var.endswith("MAGICC Fossil and Industrial")
            assert "|{}|".format(openscm_var_name) in openscm_var
        elif suffix_part_1 == "B":
            assert openscm_var.endswith("MAGICC AFOLU")
            assert "|{}|".format(openscm_var_name) in openscm_var
        else:
            assert openscm_var.endswith(openscm_var_name)


@pytest.mark.parametrize("suffix", ["CONC", "OT", "EMIS", "INVERSE_EMIS"])
@pytest.mark.parametrize(
    "suffix_part_1",
    [
        "I",
        "B",
        "T",
    ],
)
@pytest.mark.parametrize("variable", ["OC", "BC", "SOX", "NO3"])
def test_aerosols_not_rf(variable, suffix_part_1, suffix):
    openscm_var = convert_magicc7_to_openscm_variables(
        "{}{}_{}".format(variable, suffix_part_1, suffix)
    )

    assert "Aerosols|Direct Effect" not in openscm_var
    if suffix == "CONC":
        assert openscm_var.startswith("Atmospheric Concentrations")
    elif suffix == "OT":
        assert openscm_var.startswith("Optical Thickness")
    elif suffix == "EMIS":
        assert openscm_var.startswith("Emissions")
    elif suffix == "INVERSE_EMIS":
        assert openscm_var.startswith("Inverse Emissions")

    openscm_var_name = variable if variable != "SOX" else "SOx"
    if suffix_part_1 == "I":
        assert openscm_var.endswith("MAGICC Fossil and Industrial")
        assert "|{}|".format(openscm_var_name) in openscm_var
    elif suffix_part_1 == "B":
        assert openscm_var.endswith("MAGICC AFOLU")
        assert "|{}|".format(openscm_var_name) in openscm_var
    else:
        assert openscm_var.endswith(openscm_var_name)


@pytest.mark.parametrize("suffix", ["RF", "ERF", "CONC", "OT", "EMIS"])
@pytest.mark.parametrize(
    "prefix",
    [
        "I",
        "B",
        "T",
    ],
)
@pytest.mark.parametrize(
    "variable",
    [
        "CO2",
        "N2O",
        "CH4",
    ],
)
def test_ch4_co2_n2o(variable, prefix, suffix):
    openscm_var = convert_magicc7_to_openscm_variables(
        "{}{}_{}".format(variable, prefix, suffix)
    )

    if suffix == "RF":
        assert openscm_var.startswith("Radiative Forcing")
    elif suffix == "ERF":
        assert openscm_var.startswith("Effective Radiative Forcing")
    elif suffix == "CONC":
        assert openscm_var.startswith("Atmospheric Concentrations")
    elif suffix == "OT":
        assert openscm_var.startswith("Optical Thickness")

    if prefix == "I":
        assert openscm_var.endswith("MAGICC Fossil and Industrial")
        assert "|{}|".format(variable) in openscm_var
    elif prefix == "B":
        assert openscm_var.endswith("MAGICC AFOLU")
        assert "|{}|".format(variable) in openscm_var
    else:
        assert openscm_var.endswith(variable)


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
        ("CO2_EMIS", "Emissions|CO2"),
        ("CO2T_EMIS", "Emissions|CO2"),
        ("CH4_EMIS", "Emissions|CH4"),
        ("CH4T_EMIS", "Emissions|CH4"),
        ("N2O_EMIS", "Emissions|N2O"),
        ("N2OT_EMIS", "Emissions|N2O"),
        (
            "CO2PF_EMIS",
            "Net Land to Atmosphere Flux|CO2|Earth System Feedbacks|Permafrost",
        ),
        (
            "CH4PF_EMIS",
            "Net Land to Atmosphere Flux|CH4|Earth System Feedbacks|Permafrost",
        ),
        ("SURFACE_TEMP", "Surface Temperature"),
        ("SURFACE_TEMP_SUBANNUAL", "Surface Temperature"),
        ("CC4F8_CONC", "Atmospheric Concentrations|cC4F8"),
        ("AIR_CIRRUS_RF", "Radiative Forcing|Aviation|Cirrus"),
        ("AIR_CIRRUS_ERF", "Effective Radiative Forcing|Aviation|Cirrus"),
        ("AIR_CONTRAIL_RF", "Radiative Forcing|Aviation|Contrail"),
        ("AIR_CONTRAIL_ERF", "Effective Radiative Forcing|Aviation|Contrail"),
        ("AIR_H2O_RF", "Radiative Forcing|Aviation|H2O"),
        ("AIR_H2O_ERF", "Effective Radiative Forcing|Aviation|H2O"),
        # ("CH4CLATHRATE_EMIS", "Emissions|CH4|???")
        ("CH4_ERF", "Effective Radiative Forcing|CH4"),
        ("GHG_ERF", "Effective Radiative Forcing|Greenhouse Gases"),
        ("FGASSUM_ERF", "Effective Radiative Forcing|F-Gases"),
        ("TOTAL_ANTHRO_ERF", "Effective Radiative Forcing|Anthropogenic"),
        ("TOTAER_DIR_ERF", "Effective Radiative Forcing|Aerosols|Direct Effect"),
        ("CLOUD_TOT_ERF", "Effective Radiative Forcing|Aerosols|Indirect Effect"),
        ("AEROSOL_ERF", "Effective Radiative Forcing|Aerosols"),
        ("AEROSOL_RF", "Radiative Forcing|Aerosols"),
        (
            "CH4OXSTRATH2O_ERF",
            "Effective Radiative Forcing|CH4 Oxidation Stratospheric H2O",
        ),
        ("LANDUSE_ERF", "Effective Radiative Forcing|Land-use Change"),
        ("STRATOZ_ERF", "Effective Radiative Forcing|Stratospheric Ozone"),
        ("TROPOZ_ERF", "Effective Radiative Forcing|Tropospheric Ozone"),
        ("KYOTOGHG_ERF", "Effective Radiative Forcing|Greenhouse Gases|Kyoto Gases"),
        (
            "AIR_CONTRAILANDCIRRUS_ERF",
            "Effective Radiative Forcing|Aviation|Contrail and Cirrus",
        ),
        (
            "BIOMASSAER_ERF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|MAGICC AFOLU",
        ),
        (
            "MINERALDUST_ERF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|Mineral Dust",
        ),
        (
            "OCI_ERF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|OC|MAGICC Fossil and Industrial",
        ),
        (
            "OCT_ERF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|OC",
        ),
        (
            "OC_ERF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|OC",
        ),
        (
            "BCI_ERF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|BC|MAGICC Fossil and Industrial",
        ),
        (
            "BCT_ERF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|BC",
        ),
        (
            "BC_ERF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|BC",
        ),
        (
            "SOXI_ERF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|SOx|MAGICC Fossil and Industrial",
        ),
        (
            "SOXT_ERF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|SOx",
        ),
        (
            "SOX_ERF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|SOx",
        ),
        (
            "NOXI_ERF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|NOx|MAGICC Fossil and Industrial",
        ),
        (
            "NH3I_ERF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|NH3|MAGICC Fossil and Industrial",
        ),
        ("OZTOTAL_ERF", "Effective Radiative Forcing|Ozone"),
        ("TOTAL_INCLVOLCANIC_ERF", "Effective Radiative Forcing"),
        ("SLR_TOT", "Sea Level Rise"),
        ("CO2T_EMIS", "Emissions|CO2"),
        ("CH4T_RF", "Radiative Forcing|CH4"),
        ("CH4_RF", "Radiative Forcing|CH4"),
        ("NOX_EMIS", "Emissions|NOx"),
        ("NOXT_EMIS", "Emissions|NOx"),
        ("HEAT_EARTH", "Heat Content"),
        ("HEATUPTK_EARTH", "Heat Uptake"),
        ("HEAT_NONOCEAN", "Heat Content|Non-Ocean"),
        ("HEATUPTK_NONOCEAN", "Heat Uptake|Non-Ocean"),
        ("HEATCONTENT_AGGREG_TOTAL", "Heat Content|Ocean"),
        ("HEATUPTK_AGGREG", "Heat Uptake|Ocean"),
        ("SURFACE_MIXEDLAYERTEMP", "Surface Air Ocean Blended Temperature Change"),
        ("CO2_AIR2LAND_FLUX", "Net Atmosphere to Land Flux|CO2"),
        ("CO2_AIR2OCEAN_FLUX", "Net Atmosphere to Ocean Flux|CO2"),
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
        # in reverse, get back *T_EMIS so that putting e.g. "Emissions|CO2" in
        # output variables when running actually works
        ("CO2T_EMIS", "Emissions|CO2"),
        ("CH4T_EMIS", "Emissions|CH4"),
        ("N2OT_EMIS", "Emissions|N2O"),
        (
            "CO2PF_EMIS",
            "Net Land to Atmosphere Flux|CO2|Earth System Feedbacks|Permafrost",
        ),
        (
            "CH4PF_EMIS",
            "Net Land to Atmosphere Flux|CH4|Earth System Feedbacks|Permafrost",
        ),
        ("SURFACE_TEMP", "Surface Temperature"),
        ("CC4F8_CONC", "Atmospheric Concentrations|cC4F8"),
        ("AIR_CIRRUS_RF", "Radiative Forcing|Aviation|Cirrus"),
        ("AIR_CONTRAIL_RF", "Radiative Forcing|Aviation|Contrail"),
        ("AIR_H2O_RF", "Radiative Forcing|Aviation|H2O"),
        ("CH4_ERF", "Effective Radiative Forcing|CH4"),
        ("GHG_ERF", "Effective Radiative Forcing|Greenhouse Gases"),
        ("FGASSUM_ERF", "Effective Radiative Forcing|F-Gases"),
        ("TOTAL_ANTHRO_ERF", "Effective Radiative Forcing|Anthropogenic"),
        ("TOTAER_DIR_ERF", "Effective Radiative Forcing|Aerosols|Direct Effect"),
        ("CLOUD_TOT_ERF", "Effective Radiative Forcing|Aerosols|Indirect Effect"),
        ("AEROSOL_ERF", "Effective Radiative Forcing|Aerosols"),
        ("AEROSOL_RF", "Radiative Forcing|Aerosols"),
        (
            "CH4OXSTRATH2O_ERF",
            "Effective Radiative Forcing|CH4 Oxidation Stratospheric H2O",
        ),
        ("LANDUSE_ERF", "Effective Radiative Forcing|Land-use Change"),
        ("STRATOZ_ERF", "Effective Radiative Forcing|Stratospheric Ozone"),
        ("TROPOZ_ERF", "Effective Radiative Forcing|Tropospheric Ozone"),
        ("KYOTOGHG_ERF", "Effective Radiative Forcing|Greenhouse Gases|Kyoto Gases"),
        (
            "AIR_CONTRAILANDCIRRUS_ERF",
            "Effective Radiative Forcing|Aviation|Contrail and Cirrus",
        ),
        (
            "BIOMASSAER_ERF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|MAGICC AFOLU",
        ),
        (
            "MINERALDUST_ERF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|Mineral Dust",
        ),
        (
            "OCI_ERF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|OC|MAGICC Fossil and Industrial",
        ),
        (
            "OCT_ERF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|OC",
        ),
        (
            "BCI_ERF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|BC|MAGICC Fossil and Industrial",
        ),
        (
            "BCT_ERF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|BC",
        ),
        (
            "SOXI_ERF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|SOx|MAGICC Fossil and Industrial",
        ),
        (
            "SOXT_ERF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|SOx",
        ),
        (
            "NOXI_ERF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|NOx|MAGICC Fossil and Industrial",
        ),
        (
            "NO3I_ERF",
            "Effective Radiative Forcing|Aerosols|Direct Effect|NO3|MAGICC Fossil and Industrial",
        ),
        ("OZTOTAL_ERF", "Effective Radiative Forcing|Ozone"),
        ("TOTAL_INCLVOLCANIC_ERF", "Effective Radiative Forcing"),
        ("TOTAL_INCLVOLCANIC_EFFRF", "TOTAL_INCLVOLCANIC_EFFRF"),
        ("CH4_EFFRF", "CH4_EFFRF"),
        ("SLR_TOT", "Sea Level Rise"),
        ("HEAT_EARTH", "Heat Content"),
        ("HEATUPTK_EARTH", "Heat Uptake"),
        ("HEAT_NONOCEAN", "Heat Content|Non-Ocean"),
        ("HEATUPTK_NONOCEAN", "Heat Uptake|Non-Ocean"),
        ("HEATCONTENT_AGGREG_TOTAL", "Heat Content|Ocean"),
        ("HEATUPTK_AGGREG", "Heat Uptake|Ocean"),
        ("SURFACE_MIXEDLAYERTEMP", "Surface Air Ocean Blended Temperature Change"),
        ("CO2_AIR2LAND_FLUX", "Net Atmosphere to Land Flux|CO2"),
        ("CO2_AIR2OCEAN_FLUX", "Net Atmosphere to Ocean Flux|CO2"),
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
        ("AR6-NZ", "World|AR6|NZ"),
        ("AR6-NEN", "World|AR6|NEN"),
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
