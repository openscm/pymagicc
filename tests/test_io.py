from os import remove, listdir
from os.path import join, isfile, basename
from copy import deepcopy
import warnings
from unittest.mock import patch, MagicMock
import datetime
import shutil
import filecmp


import numpy as np
import pandas as pd
import re
import pytest
import f90nml
from openscm.scmdataframebase import ScmDataFrameBase


import pymagicc.definitions
from pymagicc import MAGICC6
from pymagicc.io import (
    MAGICCData,
    _Reader,
    _ConcInReader,
    _ScenWriter,
    read_cfg_file,
    get_special_scen_code,
    NoReaderWriterError,
    InvalidTemporalResError,
    pull_cfg_from_parameters_out_file,
    pull_cfg_from_parameters_out,
    get_generic_rcp_name,
    join_timeseries,
    _join_timeseries_mdata,
    determine_tool,
)
from .conftest import MAGICC6_DIR, TEST_DATA_DIR, TEST_OUT_DIR, EXPECTED_FILES_DIR


# Not all files can be read in
TEST_OUT_FILES = listdir(TEST_OUT_DIR)

INVALID_OUT_FILES = [
    r"CARBONCYCLE.*OUT",
    r".*SUBANN.*BINOUT",
    r"DAT_VOLCANIC_RF\.BINOUT",
    r"PF.*OUT",
    r"DATBASKET_.*",
    r"PRECIPINPUT.*OUT",
    r"TEMP_OCEANLAYERS.*\.BINOUT",
    r"INVERSEEMIS\.BINOUT",
    r".*INVERSE\_.*EMIS.*OUT",
    r"TIMESERIESMIX.*OUT",
    r"SUMMARY_INDICATORS.OUT",
]


def generic_mdata_tests(mdata):
    "Resusable tests to ensure data format."
    assert mdata.is_loaded == True

    assert isinstance(mdata, ScmDataFrameBase)
    pd.testing.assert_index_equal(
        mdata.meta.columns,
        pd.Index(
            ["model", "scenario", "region", "variable", "unit", "climate_model", "todo"]
        ),
    )

    assert mdata["variable"].dtype == "object"
    assert mdata["todo"].dtype == "object"
    assert mdata["unit"].dtype == "object"
    assert mdata["region"].dtype == "object"
    assert mdata["scenario"].dtype == "object"
    assert mdata["model"].dtype == "object"
    assert mdata["climate_model"].dtype == "object"

    for key in ["units", "unit", "firstdatarow", "dattype"]:
        with pytest.raises(KeyError):
            mdata.metadata[key]
    assert isinstance(mdata.metadata["header"], str)


def assert_mdata_value(mdata, value, **kwargs):
    res = mdata.filter(**kwargs)
    assert len(res) == 1
    if value < 0.1:
        np.testing.assert_allclose(res.timeseries().iloc[0], value, rtol=1e-4)
    else:
        np.testing.assert_allclose(res.timeseries().iloc[0], value)


def test_cant_find_reader_writer():
    test_name = "HISTRCP_CO2I_EMIS.txt"

    expected_message = (
        r"^"
        + re.escape("Couldn't find appropriate reader for {}.".format(test_name))
        + r"\n"
        + re.escape(
            "The file must be one "
            "of the following types and the filepath must match its "
            "corresponding regular expression:"
        )
        + r"(\n.*)*"  # dicts aren't ordered in Python3.5
        + re.escape("SCEN: ^.*\\.SCEN$")
        + r"(\n.*)*$"
    )

    with pytest.raises(NoReaderWriterError, match=expected_message):
        determine_tool(join(TEST_DATA_DIR, test_name), "reader")

    expected_message = expected_message.replace("reader", "writer")
    with pytest.raises(NoReaderWriterError, match=expected_message):
        determine_tool(join(TEST_DATA_DIR, test_name), "writer")


def test_get_invalid_tool():
    junk_tool = "junk tool"
    expected_error_msg = (
        r"^\"?"
        + re.escape(
            "MAGICCData does not know how to get a {}, "
            "valid options are:".format(junk_tool)
        )
        + r".*\"?$"
    )
    with pytest.raises(KeyError, match=expected_error_msg):
        determine_tool("EXAMPLE.SCEN", junk_tool)


def test_load_magicc6_emis():
    mdata = MAGICCData(join(MAGICC6_DIR, "HISTRCP_CO2I_EMIS.IN"))
    assert mdata.is_loaded == True
    generic_mdata_tests(mdata)

    assert_mdata_value(
        mdata,
        1.7682027e000,
        variable="Emissions|CO2|MAGICC Fossil and Industrial",
        region="World|R5ASIA",
        year=2000,
        unit="Gt C / yr",
        todo="SET",
    )


def test_load_magicc6_emis_hyphen_in_units():
    mdata = MAGICCData(join(MAGICC6_DIR, "HISTRCP_N2OI_EMIS.IN"))
    generic_mdata_tests(mdata)

    assert_mdata_value(
        mdata,
        0.288028519,
        variable="Emissions|N2O|MAGICC Fossil and Industrial",
        region="World|R5ASIA",
        year=2000,
        unit="Mt N2ON / yr",
        todo="SET",
    )


def test_load_magicc5_emis():
    mdata = MAGICCData(join(MAGICC6_DIR, "MARLAND_CO2I_EMIS.IN"))
    generic_mdata_tests(mdata)

    assert_mdata_value(
        mdata,
        6.20403698,
        variable="Emissions|CO2|MAGICC Fossil and Industrial",
        region="World|Northern Hemisphere",
        year=2000,
        unit="Gt C / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        0.495812385,
        variable="Emissions|CO2|MAGICC Fossil and Industrial",
        region="World|Southern Hemisphere",
        year=2002,
        unit="Gt C / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        0.0,
        variable="Emissions|CO2|MAGICC Fossil and Industrial",
        region="World|Southern Hemisphere",
        year=1751,
        unit="Gt C / yr",
        todo="SET",
    )


def test_load_magicc5_emis_not_renamed_error():
    test_path = TEST_DATA_DIR
    test_name = "MARLAND_CO2_EMIS_FOSSIL&IND.IN"

    expected_error_msg = re.escape(
        "Cannot determine variable from filepath: {}".format(join(test_path, test_name))
    )
    with pytest.raises(ValueError, match=expected_error_msg):
        MAGICCData(join(test_path, test_name))


def test_load_magicc6_conc():
    mdata = MAGICCData(join(MAGICC6_DIR, "HISTRCP_CO2_CONC.IN"))

    assert (mdata["unit"] == "ppm").all()
    generic_mdata_tests(mdata)
    assert_mdata_value(
        mdata,
        2.80435733e002,
        variable="Atmospheric Concentrations|CO2",
        region="World",
        year=1048,
        unit="ppm",
        todo="SET",
    )


def test_load_magicc6_conc_old_style_name_umlaut_metadata():
    mdata = MAGICCData(join(MAGICC6_DIR, "HISTRCP_HFC245fa_CONC.IN"))

    assert (mdata["unit"] == "ppt").all()
    assert mdata.metadata["data"] == "Global average mixing ratio"
    generic_mdata_tests(mdata)
    assert_mdata_value(
        mdata,
        0.0,
        variable="Atmospheric Concentrations|HFC245fa",
        region="World",
        year=2000,
        unit="ppt",
        todo="SET",
    )


def test_load_magicc6_conc_old_style_name_with_hyphen():
    mdata = MAGICCData(join(MAGICC6_DIR, "HISTRCP_HFC43-10_CONC.IN"))

    assert (mdata["unit"] == "ppt").all()
    generic_mdata_tests(mdata)
    assert_mdata_value(
        mdata,
        0.0,
        variable="Atmospheric Concentrations|HFC4310",
        region="World",
        year=2000,
        unit="ppt",
        todo="SET",
    )


def test_load_magicc7_emis_umlaut_metadata():
    mdata = MAGICCData(join(TEST_DATA_DIR, "HISTSSP_CO2I_EMIS.IN"))

    generic_mdata_tests(mdata)
    assert (
        mdata.metadata["contact"]
        == "Zebedee Nicholls, Australian-German Climate and Energy College, University of Melbourne, zebedee.nicholls@climate-energy-college.org"
    )
    assert mdata.metadata["description"] == "Test line by näme with ümlauts ëh ça"
    assert (mdata["unit"] == "Gt C / yr").all()

    assert_mdata_value(
        mdata,
        0.6638,
        variable="Emissions|CO2|MAGICC Fossil and Industrial",
        region="World|R6REF",
        year=2013,
        unit="Gt C / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        1.6911,
        variable="Emissions|CO2|MAGICC Fossil and Industrial",
        region="World|R6ASIA",
        year=2000,
        unit="Gt C / yr",
        todo="SET",
    )


def test_load_ot():
    mdata = MAGICCData(join(MAGICC6_DIR, "MIXED_NOXI_OT.IN"))

    generic_mdata_tests(mdata)

    assert mdata.metadata["data"] == "Optical Thickness"
    assert (
        mdata.metadata["description"]
        == "the land/ocean ratio of optical depth of NOXI is scaled with the hemispheric EDGAR NOXI emissions. NOXI opt. depth as available on http://www.giss.nasa.gov/data/simodel/trop.aer/"
    )
    assert (
        mdata.metadata["source"]
        == "Mixed: EDGAR: www.mnp.nl; NASA-GISS: http://data.giss.nasa.gov/"
    )
    assert (
        mdata.metadata["compiled by"]
        == "Malte Meinshausen, Lauder NZ, NCAR/PIK, malte.meinshausen@gmail.com"
    )
    assert mdata.metadata["date"] == "18-Jul-2006 11:02:48"
    assert mdata.metadata["unit normalisation"] == "Normalized to 1 in year 2000"

    assert (mdata["unit"] == "dimensionless").all()
    assert (mdata["todo"] == "SET").all()
    assert (
        mdata["variable"] == "Optical Thickness|NOx|MAGICC Fossil and Industrial"
    ).all()

    assert_mdata_value(
        mdata,
        0.00668115649,
        variable="Optical Thickness|NOx|MAGICC Fossil and Industrial",
        region="World|Northern Hemisphere|Ocean",
        year=1765,
        unit="dimensionless",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        0.526135104,
        variable="Optical Thickness|NOx|MAGICC Fossil and Industrial",
        region="World|Northern Hemisphere|Land",
        year=1865,
        unit="dimensionless",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        0.612718845,
        variable="Optical Thickness|NOx|MAGICC Fossil and Industrial",
        region="World|Southern Hemisphere|Ocean",
        year=1965,
        unit="dimensionless",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        3.70378,
        variable="Optical Thickness|NOx|MAGICC Fossil and Industrial",
        region="World|Southern Hemisphere|Land",
        year=2000,
        unit="dimensionless",
        todo="SET",
    )


def test_load_rf():
    mdata = MAGICCData(join(MAGICC6_DIR, "GISS_BCB_RF.IN"))

    generic_mdata_tests(mdata)

    assert mdata.metadata["data"] == "Radiative Forcing"
    assert (
        mdata.metadata["description"]
        == "BCB - Radiative Forcing of year 2000 (as provided on http://data.giss.nasa.gov/efficacy/) for four MAGICC boxes; scaled over time with optical thickness of file giss_bcb_ot"
    )
    assert (
        mdata.metadata["source"]
        == "Original-GISS-Description:  NET RADIA. AT   0 MB (W/M+2) ANN  E2BCBx6a-E2AarM20A (yr 1850->2000 dBCB*6 - adj"
    )
    assert (
        mdata.metadata["compiled by"]
        == "Malte Meinshausen, Lauder NZ, NCAR/PIK, malte.meinshausen@gmail.com"
    )
    assert mdata.metadata["date"] == "18-Jul-2006 11:05:18"

    assert (mdata["unit"] == "W / m^2").all()
    assert (mdata["todo"] == "SET").all()
    assert (mdata["variable"] == "Radiative Forcing|BC|MAGICC AFOLU").all()

    assert_mdata_value(
        mdata,
        0.0,
        variable="Radiative Forcing|BC|MAGICC AFOLU",
        region="World|Northern Hemisphere|Ocean",
        year=1765,
        # unit="W / m^2",  # bug, can't use ^ in filter now as regexp means it looks for not, propose removing such behaviour in pyam based on usefulness of units and fact that complicated regexp can be re-enabled with regexp=True
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        0.268436597,
        variable="Radiative Forcing|BC|MAGICC AFOLU",
        region="World|Northern Hemisphere|Land",
        year=1865,
        # unit="W / m^2",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        0.443357552,
        variable="Radiative Forcing|BC|MAGICC AFOLU",
        region="World|Southern Hemisphere|Ocean",
        year=1965,
        # unit="W / m^2",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        1.53987244,
        variable="Radiative Forcing|BC|MAGICC AFOLU",
        region="World|Southern Hemisphere|Land",
        year=2000,
        # unit="W / m^2",
        todo="SET",
    )


def test_load_solar_rf():
    mdata = MAGICCData(join(MAGICC6_DIR, "HISTRCP6SCP6to45_SOLAR_RF.IN"))

    generic_mdata_tests(mdata)

    assert mdata.metadata["data"] == "Radiative Forcing, kept constant after 2250"
    assert (
        mdata.metadata["description"]
        == "Solar irradiance by Lean et al. as recommended for CMIP5, as documented here: http://www.geo.fu-berlin.de/en/met/ag/strat/forschung/SOLARIS/Input_data/CMIP5_solar_irradiance.html - converted into radiative forcing by dividing by 4 (geometrical) and multiplying by 0.7 (albedo) effect. Furthermore, the data is normalized to have an average zero around 1750 (22 years around 1750)."
    )
    # second definition of metadata wins out
    assert (
        mdata.metadata["source"]
        == "RCP data as presented on http://www.iiasa.ac.at/web-apps/tnt/RcpDb, August 2009"
    )
    assert (
        mdata.metadata["compiled by"]
        == "Malte Meinshausen, malte.meinshausen@pik-potsdam.de, www.primap.org"
    )
    assert mdata.metadata["date"] == "24-Jul-2009 17:05:30"

    assert (mdata["unit"] == "W / m^2").all()
    assert (mdata["todo"] == "SET").all()
    assert (mdata["variable"] == "Radiative Forcing|Solar").all()
    assert (mdata["region"] == "World").all()

    assert_mdata_value(
        mdata,
        0.0149792391,
        variable="Radiative Forcing|Solar",
        region="World",
        year=1610,
        # unit="W / m^2",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        -0.00160201087,
        variable="Radiative Forcing|Solar",
        year=1865,
        # unit="W / m^2",
    )

    assert_mdata_value(
        mdata,
        0.0652917391,
        variable="Radiative Forcing|Solar",
        year=1965,
        # unit="W / m^2",
    )

    assert_mdata_value(
        mdata,
        0.0446329891,
        variable="Radiative Forcing|Solar",
        year=2183,
        # unit="W / m^2",
    )

    assert_mdata_value(
        mdata,
        0.121325148,
        variable="Radiative Forcing|Solar",
        year=2600,
        # unit="W / m^2",
    )


def test_load_volcanic_rf():
    mdata = MAGICCData(join(MAGICC6_DIR, "HIST_VOLCANIC_RF.MON"))

    generic_mdata_tests(mdata)

    assert mdata.metadata["data"] == "Radiative Forcing"
    assert (
        mdata.metadata["description"]
        == "Monthly Volcanic radiative forcing - relative / unscaled - as in NASA GISS model, using a optical thickness to radiative forcing conversion of -23.5"
    )
    # second definition of metadata wins out
    assert mdata.metadata["source"] == "NASA-GISS: http://data.giss.nasa.gov/"
    assert (
        mdata.metadata["compiled by"]
        == "Malte Meinshausen, Lauder NZ, NCAR/PIK, malte.meinshausen@gmail.com, manually extended by zero forcing from 2001 to 2006"
    )
    assert mdata.metadata["date"] == "15-Jun-2006 00:20:54"

    assert (mdata["unit"] == "W / m^2").all()
    assert (mdata["todo"] == "SET").all()
    assert (mdata["variable"] == "Radiative Forcing|Volcanic").all()

    assert_mdata_value(
        mdata,
        0.0,
        variable="Radiative Forcing|Volcanic",
        region="World|Northern Hemisphere|Land",
        year=1000,
        month=1,
        # unit="W / m^2",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        -0.0187500000,
        variable="Radiative Forcing|Volcanic",
        region="World|Northern Hemisphere|Land",
        year=1002,
        month=7,
        # unit="W / m^2",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        0.0,
        variable="Radiative Forcing|Volcanic",
        region="World|Northern Hemisphere|Ocean",
        year=1013,
        month=3,
        # unit="W / m^2",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        -0.222916667,
        variable="Radiative Forcing|Volcanic",
        region="World|Southern Hemisphere|Ocean",
        year=1119,
        month=4,
        # unit="W / m^2",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        0.0,
        variable="Radiative Forcing|Volcanic",
        region="World|Southern Hemisphere|Land",
        year=2006,
        month=12,
        # unit="W / m^2",
        todo="SET",
    )


def test_load_scen():
    mdata = MAGICCData(join(MAGICC6_DIR, "RCP26.SCEN"))

    generic_mdata_tests(mdata)

    assert (mdata["model"] == "unspecified").all()
    assert (mdata["scenario"] == "unspecified").all()
    assert (mdata["climate_model"] == "unspecified").all()
    assert (
        mdata.metadata["date"]
        == "26/11/2009 11:29:06; MAGICC-VERSION: 6.3.09, 25 November 2009"
    )
    assert "Final RCP3PD with constant emissions" in mdata.metadata["header"]

    assert_mdata_value(
        mdata,
        6.7350,
        variable="Emissions|CO2|MAGICC Fossil and Industrial",
        region="World",
        year=2000,
        unit="Gt C / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        7.5487,
        variable="Emissions|N2O",
        region="World",
        year=2002,
        unit="Mt N2ON / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        0.6470,
        variable="Emissions|HFC4310",
        region="World",
        year=2001,
        unit="kt HFC4310 / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        11.9769,
        variable="Emissions|SOx",
        region="World|R5OECD",
        year=2005,
        unit="Mt S / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        18.2123,
        variable="Emissions|NMVOC",
        region="World|R5OECD",
        year=2050,
        unit="Mt NMVOC / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        0,
        variable="Emissions|HFC23",
        region="World|R5REF",
        year=2100,
        unit="kt HFC23 / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        33.3635,
        variable="Emissions|HFC143a",
        region="World|R5ASIA",
        year=2040,
        unit="kt HFC143a / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        0.8246,
        variable="Emissions|SF6",
        region="World|R5ASIA",
        year=2040,
        unit="kt SF6 / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        -0.0125,
        variable="Emissions|CO2|MAGICC AFOLU",
        region="World|R5MAF",
        year=2050,
        unit="Gt C / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        37.6218,
        variable="Emissions|CH4",
        region="World|R5MAF",
        year=2070,
        unit="Mt CH4 / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        1.8693,
        variable="Emissions|NOx",
        region="World|R5LAM",
        year=2080,
        unit="Mt N / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        0.4254,
        variable="Emissions|BC",
        region="World|R5LAM",
        year=2090,
        unit="Mt BC / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        0,
        variable="Emissions|NH3",
        region="World|Bunkers",
        year=2000,
        unit="Mt N / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        0.0,
        variable="Emissions|SF6",
        region="World|Bunkers",
        year=2002,
        unit="kt SF6 / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        5.2133,
        variable="Emissions|HFC125",
        region="World|R5REF",
        year=2125,
        unit="kt HFC125 / yr",
        todo="SET",
    )


def test_load_scen_specify_metadata():
    tmodel = "MESSAGE"
    tscenario = "RCP45"
    tclimate_model = "MAGICC6"

    mdata = MAGICCData(
        join(MAGICC6_DIR, "RCP26.SCEN"),
        columns={
            "model": [tmodel],
            "scenario": [tscenario],
            "climate_model": [tclimate_model],
        },
    )

    generic_mdata_tests(mdata)

    assert (mdata["model"] == tmodel).all()
    assert (mdata["scenario"] == tscenario).all()
    assert (mdata["climate_model"] == tclimate_model).all()


def test_load_scen_year_first_column():
    mdata = MAGICCData(join(TEST_DATA_DIR, "RCP26_WORLD_ONLY_YEAR_FIRST_COLUMN.SCEN"))

    generic_mdata_tests(mdata)

    assert "Generic text" in mdata.metadata["header"]

    assert_mdata_value(
        mdata,
        6.7350,
        variable="Emissions|CO2|MAGICC Fossil and Industrial",
        region="World",
        year=2000,
        unit="Gt C / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        7.5487,
        variable="Emissions|N2O",
        region="World",
        year=2002,
        unit="Mt N2ON / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        0.6470,
        variable="Emissions|HFC4310",
        region="World",
        year=2001,
        unit="kt HFC4310 / yr",
        todo="SET",
    )


@patch("pymagicc.io._ScenReader._read_data_header_line")
def test_load_scen_last_resort_message(mock_scen_header_line_reader):
    mock_scen_header_line_reader.side_effect = AssertionError

    error_msg = re.escape(
        "This is unexpected, please raise an issue on "
        "https://github.com/openclimatedata/pymagicc/issues"
    )
    with pytest.raises(Exception, match=error_msg):
        MAGICCData(join(MAGICC6_DIR, "RCP26.SCEN"))


def test_load_scen_sres():
    mdata = MAGICCData(join(MAGICC6_DIR, "SRESA1B.SCEN"))

    generic_mdata_tests(mdata)

    assert "Antero Hot Springs" in mdata.metadata["header"]

    assert_mdata_value(
        mdata,
        6.8963,
        variable="Emissions|CO2|MAGICC Fossil and Industrial",
        region="World",
        year=2000,
        unit="Gt C / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        6.6751,
        variable="Emissions|N2O",
        region="World",
        year=1990,
        unit="Mt N2ON / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        0,
        variable="Emissions|HFC4310",
        region="World",
        year=2000,
        unit="kt HFC4310 / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        9.8762,
        variable="Emissions|SOx",
        region="World|OECD90",
        year=2010,
        unit="Mt S / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        28.1940,
        variable="Emissions|NMVOC",
        region="World|OECD90",
        year=2050,
        unit="Mt NMVOC / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        0.0624,
        variable="Emissions|HFC23",
        region="World|REF",
        year=2100,
        unit="kt HFC23 / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        5.4067,
        variable="Emissions|HFC125",
        region="World|REF",
        year=2100,
        unit="kt HFC125 / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        15.4296,
        variable="Emissions|HFC143a",
        region="World|ASIA",
        year=2040,
        unit="kt HFC143a / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        6.4001,
        variable="Emissions|SF6",
        region="World|ASIA",
        year=2040,
        unit="kt SF6 / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        0.2613,
        variable="Emissions|CO2|MAGICC AFOLU",
        region="World|ALM",
        year=2050,
        unit="Gt C / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        130.1256,
        variable="Emissions|CH4",
        region="World|ALM",
        year=2070,
        unit="Mt CH4 / yr",
        todo="SET",
    )


def test_load_scen7():
    mdata = MAGICCData(join(TEST_DATA_DIR, "TESTSCEN7.SCEN7"))

    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "13-Oct-2017 16:45:35"
    assert mdata.metadata["description"] == "TEST SCEN7 file"
    assert "NOTES" in mdata.metadata["header"]
    assert "~~~~~" in mdata.metadata["header"]
    assert "Some notes" in mdata.metadata["header"]

    assert_mdata_value(
        mdata,
        6.7350,
        variable="Emissions|CO2|MAGICC Fossil and Industrial",
        region="World",
        year=2000,
        unit="Gt C / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        7.5487,
        variable="Emissions|N2O|MAGICC Fossil and Industrial",
        region="World",
        year=2002,
        unit="Mt N2ON / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        10.4328,
        variable="Emissions|HFC23",
        region="World",
        year=2001,
        unit="kt HFC23 / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        11.9769,
        variable="Emissions|SOx",
        region="World|R6OECD90",
        year=2005,
        unit="Mt S / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        18.2123,
        variable="Emissions|NMVOC",
        region="World|R6OECD90",
        year=2050,
        unit="Mt NMVOC / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        0,
        variable="Emissions|HFC23",
        region="World|R6REF",
        year=2100,
        unit="kt HFC23 / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        5.2133,
        variable="Emissions|CH2Cl2",
        region="World|R6REF",
        year=2125,
        unit="kt CH2Cl2 / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        33.3635,
        variable="Emissions|HFC143a",
        region="World|R6ASIA",
        year=2040,
        unit="kt HFC143a / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        0.8246,
        variable="Emissions|SO2F2",
        region="World|R6ASIA",
        year=2040,
        unit="kt SO2F2 / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        -0.0125,
        variable="Emissions|CO2|MAGICC AFOLU",
        region="World|R6MAF",
        year=2050,
        unit="Gt C / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        37.6218,
        variable="Emissions|CH4",
        region="World|R6MAF",
        year=2070,
        unit="Mt CH4 / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        1.8693,
        variable="Emissions|NOx",
        region="World|R6LAM",
        year=2080,
        unit="Mt N / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        0.4254,
        variable="Emissions|BC|MAGICC AFOLU",
        region="World|R6LAM",
        year=2090,
        unit="Mt BC / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        0,
        variable="Emissions|NH3",
        region="World|Bunkers",
        year=2000,
        unit="Mt N / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        0,
        variable="Emissions|SO2F2",
        region="World|Bunkers",
        year=2002,
        unit="kt SO2F2 / yr",
        todo="SET",
    )


def test_load_scen7_mhalo():
    mdata = MAGICCData(join(TEST_DATA_DIR, "TEST_MHALO.SCEN7"))

    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "22-Dec-2017 18:07:18"
    assert mdata.metadata["source"] == "Raw sauce."
    assert (
        mdata.metadata["description"]
        == "This scenario file was compiled to run MAGICC."
    )
    assert "NOTES" in mdata.metadata["header"]
    assert "~~~~~" in mdata.metadata["header"]
    assert "HCFC22" in mdata.metadata["header"]

    assert_mdata_value(
        mdata,
        0.343277,
        variable="Emissions|CFC11",
        region="World",
        year=2015,
        unit="kt CFC11 / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        0.925486,
        variable="Emissions|CH3Br",
        region="World",
        year=2065,
        unit="kt CH3Br / yr",
        todo="SET",
    )

    assert_mdata_value(
        mdata,
        0.047699,
        variable="Emissions|Halon1301",
        region="World",
        year=2100,
        unit="kt Halon1301 / yr",
        todo="SET",
    )


def test_load_prn():
    mdata = MAGICCData(join(MAGICC6_DIR, "RCPODS_WMO2006_Emissions_A1.prn"))

    generic_mdata_tests(mdata)

    # top line should be ignored
    assert "16      1850      2500" not in mdata.metadata["header"]
    assert mdata.metadata["date"] == "4th September 2009"
    assert (
        mdata.metadata["description"]
        == "1951-2100 Baseline emission file generated by John Daniel and Guus Velders for WMO2006, Chapter 8. (2/3/06); earlier emisisons for CFC-11, CFC-12, CFC-113, CFC-114, CCl4 extended by John Daniel (pers. Communication, 25th"
    )
    assert (
        "ons have been adapted to match mixing ratio observations by Butler et al. 1999 with emissions starting in 1850. HCFC-142b from 2005 to 2007 adapted to Montzka et al. 2009 with emission growth/decline rates kept the same after 2007."
        in mdata.metadata["header"]
    )
    assert (mdata["region"] == "World").all()
    assert (mdata["todo"] == "SET").all()
    assert not (mdata["unit"] == "t / yr").all()

    assert_mdata_value(
        mdata, 0, variable="Emissions|CFC11", year=1850, unit="t CFC11 / yr"
    )

    assert_mdata_value(
        mdata, 444, variable="Emissions|CFC115", year=1965, unit="t CFC115 / yr"
    )

    assert_mdata_value(
        mdata, 10743, variable="Emissions|Halon1211", year=1996, unit="t Halon1211 / yr"
    )

    assert_mdata_value(
        mdata, 1062, variable="Emissions|Halon1301", year=2017, unit="t Halon1301 / yr"
    )

    assert_mdata_value(
        mdata, 3511082, variable="Emissions|CH3Cl", year=2500, unit="t CH3Cl / yr"
    )


def test_load_prn_no_units():
    mdata = MAGICCData(join(MAGICC6_DIR, "WMO2006_ODS_A1Baseline.prn"))

    generic_mdata_tests(mdata)

    # top line should be ignored
    assert "6      1950      2100" not in mdata.metadata["header"]
    assert (
        "6/19/2006A1: Baseline emission file generated by John Daniel and Guus Velders"
        in mdata.metadata["header"]
    )

    assert (mdata["region"] == "World").all()
    assert (mdata["todo"] == "SET").all()
    assert not (mdata["unit"] == "t / yr").all()

    assert_mdata_value(
        mdata, 139965, variable="Emissions|CFC12", year=1950, unit="t CFC12 / yr"
    )

    assert_mdata_value(
        mdata, 3511082, variable="Emissions|CH3Cl", year=2100, unit="t CH3Cl / yr"
    )


def test_load_prn_mixing_ratios_years_label():
    mdata = MAGICCData(join(MAGICC6_DIR, "RCPODS_WMO2006_MixingRatios_A1.prn"))

    generic_mdata_tests(mdata)

    # top line should be ignored
    assert "17      1850      2100" not in mdata.metadata["header"]
    assert mdata.metadata["data"] == "Global average mixing ratios"
    assert (
        mdata.metadata["description"]
        == "1951-2100 Baseline mixing ratio file generated by John Daniel and Guus Velders for WMO2006, Chapter 8. (2/3/06); CH3CL updated to reflect MAGICC6 timeseries after 1955 and lower 2000 concentrations closer to 535ppt in line with"
    )
    assert (mdata["region"] == "World").all()
    assert (mdata["todo"] == "SET").all()
    assert (mdata["unit"] == "ppt").all()

    assert_mdata_value(mdata, 0, variable="Atmospheric Concentrations|CFC12", year=1850)

    assert_mdata_value(
        mdata, 5.058, variable="Atmospheric Concentrations|CFC114", year=1965
    )

    assert_mdata_value(
        mdata, 13.81, variable="Atmospheric Concentrations|HCFC141b", year=2059
    )

    assert_mdata_value(
        mdata, 0.007, variable="Atmospheric Concentrations|Halon2402", year=2091
    )

    assert_mdata_value(
        mdata, 538, variable="Atmospheric Concentrations|CH3Cl", year=2100
    )


def test_load_rcp_historical_dat_emissions():
    test_file = "20THCENTURY_EMISSIONS.DAT"
    mdata = MAGICCData(join(TEST_DATA_DIR, test_file))
    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "26/11/2009 11:29:06"
    assert mdata.metadata["magicc-version"] == "6.3.09, 25 November 2009"
    assert "PRE2005__EMISSIONS" in mdata.metadata["header"]
    assert (
        "COLUMN_DESCRIPTION________________________________________"
        in mdata.metadata["header"]
    )

    assert (mdata["variable"].str.startswith("Emissions|")).all()
    assert (mdata["region"] == "World").all()
    assert (mdata["todo"] == "SET").all()

    assert_mdata_value(
        mdata,
        0.003,
        variable="Emissions|CO2|MAGICC Fossil and Industrial",
        region="World",
        year=1766,
        unit="Gt C / yr",
    )

    assert_mdata_value(
        mdata,
        2.4364481,
        variable="Emissions|CH4",
        region="World",
        year=1767,
        unit="Mt CH4 / yr",
    )

    assert_mdata_value(
        mdata,
        3511.0820,
        variable="Emissions|CH3Cl",
        region="World",
        year=2005,
        unit="kt CH3Cl / yr",
    )


def test_load_rcp_historical_dat_concentrations():
    test_file = "20THCENTURY_MIDYEAR_CONCENTRATIONS.DAT"
    mdata = MAGICCData(join(TEST_DATA_DIR, test_file))

    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "26/11/2009 11:29:06"
    assert mdata.metadata["magicc-version"] == "6.3.09, 25 November 2009"
    assert "PRE2005__MIDYEAR__CONCENTRATIONS" in mdata.metadata["header"]
    assert (
        "COLUMN_DESCRIPTION________________________________________"
        in mdata.metadata["header"]
    )

    assert (mdata["variable"].str.startswith("Atmospheric Concentrations|")).all()
    assert (mdata["region"] == "World").all()
    assert (mdata["todo"] == "SET").all()

    assert_mdata_value(
        mdata,
        277.8388,
        variable="Atmospheric Concentrations|CO2 Equivalent",
        region="World",
        year=1766,
        unit="ppm",
    )

    assert_mdata_value(
        mdata,
        278.68732,
        variable="Atmospheric Concentrations|CO2 Equivalent|Kyoto Gases",
        region="World",
        year=1767,
        unit="ppm",
    )

    assert_mdata_value(
        mdata,
        126.7694,
        variable="Atmospheric Concentrations|HFC134a Equivalent|F Gases",
        region="World",
        year=2005,
        unit="ppt",
    )

    assert_mdata_value(
        mdata,
        1003.5801,
        variable="Atmospheric Concentrations|CFC12 Equivalent|Montreal Protocol Halogen Gases",
        region="World",
        year=2005,
        unit="ppt",
    )

    assert_mdata_value(
        mdata,
        538,
        variable="Atmospheric Concentrations|CH3Cl",
        region="World",
        year=2005,
        unit="ppt",
    )


def test_load_rcp_historical_dat_forcings():
    test_file = "20THCENTURY_MIDYEAR_RADFORCING.DAT"
    mdata = MAGICCData(join(TEST_DATA_DIR, test_file))

    generic_mdata_tests(mdata)

    assert (
        mdata.metadata["date"]
        == "26/11/2009 11:29:06 (updated description, 30 May 2010)."
    )
    assert mdata.metadata["magicc-version"] == "6.3.09, 25 November 2009"
    assert "PRE2005 ends in year 2005" in mdata.metadata["header"]
    assert (
        "COLUMN_DESCRIPTION________________________________________"
        in mdata.metadata["header"]
    )

    assert (mdata["variable"].str.startswith("Radiative Forcing")).all()
    assert (mdata["region"] == "World").all()
    assert (mdata["todo"] == "SET").all()
    assert (mdata["unit"] == "W / m^2").all()

    assert_mdata_value(
        mdata,
        0.12602655,
        variable="Radiative Forcing",
        region="World",
        year=1766,
        # unit="W / m^2"
    )

    assert_mdata_value(
        mdata,
        0.0070393750,
        variable="Radiative Forcing|Solar",
        region="World",
        year=1767,
        # unit="W / m^2"
    )

    assert_mdata_value(
        mdata,
        0.10018846,
        variable="Radiative Forcing|Black Carbon on Snow",
        region="World",
        year=2005,
        # unit="W / m^2"
    )


def test_load_rcp_projections_dat_emissions():
    test_file = "RCP3PD_EMISSIONS.DAT"
    mdata = MAGICCData(join(TEST_DATA_DIR, test_file))
    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "26/11/2009 11:29:06"
    assert mdata.metadata["magicc-version"] == "6.3.09, 25 November 2009"
    assert "RCP3PD__EMISSIONS" in mdata.metadata["header"]
    assert (
        "COLUMN_DESCRIPTION________________________________________"
        in mdata.metadata["header"]
    )

    assert (mdata["variable"].str.startswith("Emissions|")).all()
    assert (mdata["region"] == "World").all()
    assert (mdata["todo"] == "SET").all()

    assert_mdata_value(
        mdata,
        -0.9308,
        variable="Emissions|CO2|MAGICC Fossil and Industrial",
        region="World",
        year=2100,
        unit="Gt C / yr",
    )

    assert_mdata_value(
        mdata,
        2.4364481,
        variable="Emissions|CH4",
        region="World",
        year=1767,
        unit="Mt CH4 / yr",
    )

    assert_mdata_value(
        mdata,
        3511.0820,
        variable="Emissions|CH3Cl",
        region="World",
        year=2500,
        unit="kt CH3Cl / yr",
    )


def test_load_rcp_projections_dat_concentrations():
    test_file = "RCP3PD_MIDYEAR_CONCENTRATIONS.DAT"
    mdata = MAGICCData(join(TEST_DATA_DIR, test_file))
    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "26/11/2009 11:29:06"
    assert mdata.metadata["magicc-version"] == "6.3.09, 25 November 2009"
    assert "RCP3PD__MIDYEAR__CONCENTRATIONS" in mdata.metadata["header"]
    assert (
        "COLUMN_DESCRIPTION________________________________________"
        in mdata.metadata["header"]
    )

    assert (mdata["variable"].str.startswith("Atmospheric Concentrations|")).all()
    assert (mdata["region"] == "World").all()
    assert (mdata["todo"] == "SET").all()

    assert_mdata_value(
        mdata,
        277.8388,
        variable="Atmospheric Concentrations|CO2 Equivalent",
        region="World",
        year=1766,
        unit="ppm",
    )

    assert_mdata_value(
        mdata,
        475.19275,
        variable="Atmospheric Concentrations|CO2 Equivalent|Kyoto Gases",
        region="World",
        year=2100,
        unit="ppm",
    )

    assert_mdata_value(
        mdata,
        900.02269,
        variable="Atmospheric Concentrations|HFC134a Equivalent|F Gases",
        region="World",
        year=2500,
        unit="ppt",
    )

    assert_mdata_value(
        mdata,
        10.883049,
        variable="Atmospheric Concentrations|CFC12 Equivalent|Montreal Protocol Halogen Gases",
        region="World",
        year=2500,
        unit="ppt",
    )

    assert_mdata_value(
        mdata,
        538.02891,
        variable="Atmospheric Concentrations|CH3Cl",
        region="World",
        year=2500,
        unit="ppt",
    )


def test_load_rcp_projections_dat_forcings():
    test_file = "RCP3PD_MIDYEAR_RADFORCING.DAT"
    mdata = MAGICCData(join(TEST_DATA_DIR, test_file))
    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "26/11/2009 11:29:06 (updated description)"
    assert mdata.metadata["magicc-version"] == "6.3.09, 25 November 2009"
    assert "RCP3PD__RADIATIVE FORCINGS" in mdata.metadata["header"]
    assert (
        "COLUMN_DESCRIPTION________________________________________"
        in mdata.metadata["header"]
    )

    assert (mdata["variable"].str.startswith("Radiative Forcing")).all()
    assert (mdata["region"] == "World").all()
    assert (mdata["todo"] == "SET").all()
    assert (mdata["unit"] == "W / m^2").all()

    assert_mdata_value(
        mdata,
        0.12602655,
        variable="Radiative Forcing",
        region="World",
        year=1766,
        # unit="W / m^2"
    )

    assert_mdata_value(
        mdata,
        0.11622211,
        variable="Radiative Forcing|Volcanic",
        region="World",
        year=1766,
        # unit="W / m^2"
    )

    assert_mdata_value(
        mdata,
        0.016318812,
        variable="Radiative Forcing|Anthropogenic",
        region="World",
        year=1766,
        # unit="W / m^2"
    )

    assert_mdata_value(
        mdata,
        0.015363514,
        variable="Radiative Forcing|Greenhouse Gases",
        region="World",
        year=1766,
        # unit="W / m^2"
    )

    assert_mdata_value(
        mdata,
        0.015363514,
        variable="Radiative Forcing|Greenhouse Gases|Kyoto Gases",
        region="World",
        year=1766,
        # unit="W / m^2"
    )

    assert_mdata_value(
        mdata,
        0.015363514,
        variable="Radiative Forcing|CO2, CH4 and N2O",
        region="World",
        year=1766,
        # unit="W / m^2"
    )

    assert_mdata_value(
        mdata,
        0,
        variable="Radiative Forcing|F Gases",
        region="World",
        year=1766,
        # unit="W / m^2"
    )

    assert_mdata_value(
        mdata,
        0,
        variable="Radiative Forcing|Montreal Protocol Halogen Gases",
        region="World",
        year=1766,
        # unit="W / m^2"
    )

    assert_mdata_value(
        mdata,
        0.000017767194,
        variable="Radiative Forcing|Aerosols|Direct Effect",
        region="World",
        year=1766,
        # unit="W / m^2"
    )

    assert_mdata_value(
        mdata,
        0.00025010344,
        variable="Radiative Forcing|Aerosols|MAGICC AFOLU",
        region="World",
        year=1766,
        # unit="W / m^2"
    )

    assert_mdata_value(
        mdata,
        -0.00019073512,
        variable="Radiative Forcing|Mineral Dust",
        region="World",
        year=1766,
        # unit="W / m^2"
    )

    assert_mdata_value(
        mdata,
        -0.00080145063,
        variable="Radiative Forcing|Aerosols|Indirect Effect",
        region="World",
        year=1766,
        # unit="W / m^2"
    )

    assert_mdata_value(
        mdata,
        0,
        variable="Radiative Forcing|Stratospheric Ozone",
        region="World",
        year=1766,
        # unit="W / m^2"
    )

    assert_mdata_value(
        mdata,
        0.0014060381,
        variable="Radiative Forcing|Tropospheric Ozone",
        region="World",
        year=1766,
        # unit="W / m^2"
    )

    assert_mdata_value(
        mdata,
        0.00060670657,
        variable="Radiative Forcing|CH4 Oxidation Stratospheric H2O",
        region="World",
        year=1766,
        # unit="W / m^2"
    )

    assert_mdata_value(
        mdata,
        -0.00038147024,
        variable="Radiative Forcing|Land-use Change",
        region="World",
        year=1766,
        # unit="W / m^2"
    )

    assert_mdata_value(
        mdata,
        0.19056187,
        variable="Radiative Forcing|Solar",
        region="World",
        year=2100,
        # unit="W / m^2"
    )

    assert_mdata_value(
        mdata,
        0.038412234,
        variable="Radiative Forcing|Black Carbon on Snow",
        region="World",
        year=2500,
        # unit="W / m^2"
    )


@pytest.mark.parametrize(
    "input, expected",
    [
        ("rCp26", "rcp26"),
        ("rCp3pd", "rcp26"),
        ("rCp45", "rcp45"),
        ("rCp6", "rcp60"),
        ("rCp60", "rcp60"),
        ("rCp85", "rcp85"),
    ],
)
def test_generic_rcp_names(input, expected):
    for tin in [input, input.upper(), input.lower()]:
        result = get_generic_rcp_name(input)
        assert result == expected


def test_generic_rcp_name_error():
    tinput = "junk"
    error_msg = re.escape("No generic name for input: {}".format(tinput))
    with pytest.raises(ValueError, match=error_msg):
        get_generic_rcp_name(tinput)


def test_load_cfg_with_magicc_input():
    test_file = "MAGCFG_BULKPARAS.CFG"
    expected_error_msg = (
        r"^"
        + re.escape("MAGCCInput cannot read .CFG files like ")
        + r".*{}".format(test_file)
        + re.escape(", please use pymagicc.io.read_cfg_file")
        + r"$"
    )

    with pytest.raises(ValueError, match=expected_error_msg):
        MAGICCData(join(MAGICC6_DIR, test_file))


def test_load_cfg():
    cfg = read_cfg_file(join(MAGICC6_DIR, "MAGCFG_BULKPARAS.CFG"))

    assert cfg["NML_BULKPARALIST"]["BULKOUT_NRUNS"] == 190
    assert cfg["NML_BULKPARALIST"]["BULKOUT_N_INDICATORS"] == 323
    assert cfg["NML_BULKPARALIST"]["BULKOUT_CRASHED_RESULTVALUE"] == -999.999

    cfg = read_cfg_file(join(MAGICC6_DIR, "MAGCFG_DEFAULTALL_69.CFG"))

    assert cfg["NML_YEARS"]["STARTYEAR"] == 1500
    assert cfg["NML_YEARS"]["ENDYEAR"] == 4200
    assert cfg["NML_YEARS"]["STEPSPERYEAR"] == 12

    assert cfg["NML_ALLCFGS"]["RUNNAME"] == "RUN001"
    assert cfg["NML_ALLCFGS"]["RUNDATE"] == "No Date specified."
    assert cfg["NML_ALLCFGS"]["CO2_FEEDBACKFACTOR_GPP"] == 0.015
    assert cfg["NML_ALLCFGS"]["CH4_INCL_CH4OX"] == 1
    assert cfg["NML_ALLCFGS"]["CH4_S"] == -0.32
    assert (
        cfg["NML_ALLCFGS"]["FILE_MHALO_CONC"]
        == "Mixing ratios WMO2002 version5b_A1.prn"
    )
    assert cfg["NML_ALLCFGS"]["GEN_RCPPLUSREGIONS2NH"] == [0.9, 1.0, 0.8, 0.6, 0.3, 0.9]
    assert cfg["NML_ALLCFGS"]["MHALO_GWP"] == [
        3800,
        8100,
        4800,
        10000,
        7370,
        1400,
        146,
        1500,
        725,
        1800,
        1890,
        0,
        5400,
        1640,
        5,
        13,
    ]
    assert cfg["NML_ALLCFGS"]["MHALO_CL_ATOMS"] == [
        3,
        2,
        3,
        2,
        1,
        4,
        3,
        1,
        2,
        1,
        1,
        0,
        0,
        0,
        0,
        1,
    ]
    assert cfg["NML_ALLCFGS"]["MHALO_NAMES"] == [
        "CFC_11",
        "CFC_12",
        "CFC_113",
        "CFC_114",
        "CFC_115",
        "CARB_TET",
        "MCF",
        "HCFC_22",
        "HCFC_141B",
        "HCFC_142B",
        "HALON1211",
        "HALON1202",
        "HALON1301",
        "HALON2402",
        "CH3BR",
        "CH3CL",
    ]
    assert cfg["NML_ALLCFGS"]["MHALO_FORMULA"] == [
        "(CCL3F)",
        "(CCL2F2)",
        "(C2CL3F3)",
        "(C2CL2F4)",
        "(C2CLF5)",
        "(CCL4)",
        "(CH3CCL3)",
        "(CHCLF2)",
        "(CH3CCL2F)",
        "(CH3CCLF2)",
        "(CF2CLBR)",
        "(CBR2F2)",
        "(CF3BR)",
        "((CF2BR)2)",
        "(CH3BR)",
        "(CH3CL)",
    ]
    assert cfg["NML_ALLCFGS"]["RF_REGIONS_STRATOZ"] == [
        -0.01189,
        -0.02267,
        -0.06251,
        -0.24036,
    ]


@pytest.mark.xfail(reason="f90nml cannot handle / in namelist properly")
def test_load_cfg_with_slash_in_units():
    cfg = read_cfg_file(join(TEST_DATA_DIR, "F90NML_BUG.CFG"))

    assert cfg["THISFILE_SPECIFICATIONS"]["THISFILE_DATACOLUMNS"] == 4
    assert cfg["THISFILE_SPECIFICATIONS"]["THISFILE_FIRSTYEAR"] == 1000
    assert cfg["THISFILE_SPECIFICATIONS"]["THISFILE_LASTYEAR"] == 2006
    assert cfg["THISFILE_SPECIFICATIONS"]["THISFILE_ANNUALSTEPS"] == 12
    assert cfg["THISFILE_SPECIFICATIONS"]["THISFILE_FIRSTDATAROW"] == 21
    # this fails
    assert cfg["THISFILE_SPECIFICATIONS"]["THISFILE_UNITS"] == "W / m^2"


@pytest.mark.parametrize(
    "test_file",
    [
        join(TEST_OUT_DIR, "DAT_SURFACE_TEMP.OUT"),
        join(TEST_DATA_DIR, "out_quoted_units", "DAT_SURFACE_TEMP.OUT"),
    ],
)
def test_load_out(test_file):
    mdata = MAGICCData(test_file)

    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "2018-09-23 18:33"
    assert (
        mdata.metadata["magicc-version"]
        == "6.8.01 BETA, 7th July 2012 - live.magicc.org"
    )
    assert "__MAGICC 6.X DATA OUTPUT FILE__" in mdata.metadata["header"]
    assert (mdata["todo"] == "N/A").all()
    assert (mdata["unit"] == "K").all()
    assert (mdata["variable"] == "Surface Temperature").all()

    assert_mdata_value(
        mdata,
        0.0079979091,
        variable="Surface Temperature",
        region="World",
        year=1767,
        unit="K",
    )

    assert_mdata_value(
        mdata,
        -0.022702952,
        variable="Surface Temperature",
        region="World",
        year=1965,
        unit="K",
    )

    assert_mdata_value(
        mdata,
        0.010526585,
        variable="Surface Temperature",
        region="World|Northern Hemisphere|Ocean",
        year=1769,
        unit="K",
    )

    assert_mdata_value(
        mdata,
        -0.25062424,
        variable="Surface Temperature",
        region="World|Southern Hemisphere|Ocean",
        year=1820,
        unit="K",
    )

    assert_mdata_value(
        mdata,
        1.8515042,
        variable="Surface Temperature",
        region="World|Northern Hemisphere|Land",
        year=2093,
        unit="K",
    )

    assert_mdata_value(
        mdata,
        0,
        variable="Surface Temperature",
        region="World|Southern Hemisphere|Land",
        year=1765,
        unit="K",
    )


def test_load_out_emis():
    mdata = MAGICCData(join(TEST_OUT_DIR, "DAT_BCB_EMIS.OUT"))

    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "2018-09-23 18:33"
    assert (
        mdata.metadata["magicc-version"]
        == "6.8.01 BETA, 7th July 2012 - live.magicc.org"
    )
    assert "__MAGICC 6.X DATA OUTPUT FILE__" in mdata.metadata["header"]
    assert (mdata["todo"] == "N/A").all()
    assert (mdata["unit"] == "Mt BC / yr").all()
    assert (mdata["variable"] == "Emissions|BC|MAGICC AFOLU").all()

    assert_mdata_value(
        mdata,
        0,
        variable="Emissions|BC|MAGICC AFOLU",
        region="World",
        year=1765,
        unit="Mt BC / yr",
    )

    assert_mdata_value(
        mdata,
        2.0025816,
        variable="Emissions|BC|MAGICC AFOLU",
        region="World",
        year=1965,
        unit="Mt BC / yr",
    )

    assert_mdata_value(
        mdata,
        0.0,
        variable="Emissions|BC|MAGICC AFOLU",
        region="World|Northern Hemisphere|Ocean",
        year=1769,
        unit="Mt BC / yr",
    )

    assert_mdata_value(
        mdata,
        0.0,
        variable="Emissions|BC|MAGICC AFOLU",
        region="World|Southern Hemisphere|Ocean",
        year=1820,
        unit="Mt BC / yr",
    )

    assert_mdata_value(
        mdata,
        0.71504927,
        variable="Emissions|BC|MAGICC AFOLU",
        region="World|Northern Hemisphere|Land",
        year=2093,
        unit="Mt BC / yr",
    )

    assert_mdata_value(
        mdata,
        0.48390716,
        variable="Emissions|BC|MAGICC AFOLU",
        region="World|Southern Hemisphere|Land",
        year=2100,
        unit="Mt BC / yr",
    )


def test_load_out_slash_and_caret_in_rf_units():
    mdata = MAGICCData(join(TEST_OUT_DIR, "DAT_SOXB_RF.OUT"))

    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "2018-09-23 18:33"
    assert (
        mdata.metadata["magicc-version"]
        == "6.8.01 BETA, 7th July 2012 - live.magicc.org"
    )
    assert "__MAGICC 6.X DATA OUTPUT FILE__" in mdata.metadata["header"]
    assert (mdata["todo"] == "N/A").all()
    assert (mdata["unit"] == "W / m^2").all()
    assert (mdata["variable"] == "Radiative Forcing|SOx|MAGICC AFOLU").all()

    assert_mdata_value(
        mdata,
        -0.00025099784,
        variable="Radiative Forcing|SOx|MAGICC AFOLU",
        region="World",
        year=1767,
        # unit="W / m^2"
    )

    assert_mdata_value(
        mdata,
        -0.032466593,
        variable="Radiative Forcing|SOx|MAGICC AFOLU",
        region="World",
        year=1965,
        # unit="W / m^2"
    )

    assert_mdata_value(
        mdata,
        -0.0014779559,
        variable="Radiative Forcing|SOx|MAGICC AFOLU",
        region="World|Northern Hemisphere|Ocean",
        year=1769,
        # unit="W / m^2"
    )

    assert_mdata_value(
        mdata,
        -0.024316933,
        variable="Radiative Forcing|SOx|MAGICC AFOLU",
        region="World|Northern Hemisphere|Land",
        year=2093,
        # unit="W / m^2"
    )

    assert_mdata_value(
        mdata,
        0,
        variable="Radiative Forcing|SOx|MAGICC AFOLU",
        region="World|Southern Hemisphere|Land",
        year=1765,
        # unit="W / m^2"
    )


def test_load_out_slash_and_caret_in_heat_content_units():
    mdata = MAGICCData(join(TEST_OUT_DIR, "DAT_HEATCONTENT_AGGREG_DEPTH1.OUT"))

    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "2018-09-23 18:33"
    assert (
        mdata.metadata["magicc-version"]
        == "6.8.01 BETA, 7th July 2012 - live.magicc.org"
    )
    assert "__MAGICC 6.X DATA OUTPUT FILE__" in mdata.metadata["header"]
    assert (mdata["todo"] == "N/A").all()
    assert (mdata["unit"] == "10^22J").all()
    assert (mdata["variable"] == "Aggregated Ocean Heat Content|Depth 1").all()

    assert_mdata_value(
        mdata,
        0.046263236,
        variable="Aggregated Ocean Heat Content|Depth 1",
        region="World",
        year=1767,
        # unit="10^22J"
    )

    assert_mdata_value(
        mdata,
        3.4193050,
        variable="Aggregated Ocean Heat Content|Depth 1",
        region="World",
        year=1965,
        # unit="10^22J"
    )

    assert_mdata_value(
        mdata,
        0.067484257,
        variable="Aggregated Ocean Heat Content|Depth 1",
        region="World|Northern Hemisphere|Ocean",
        year=1769,
        # unit="10^22J"
    )

    assert_mdata_value(
        mdata,
        -4.2688102,
        variable="Aggregated Ocean Heat Content|Depth 1",
        region="World|Southern Hemisphere|Ocean",
        year=1820,
        # unit="10^22J"
    )

    assert_mdata_value(
        mdata,
        0,
        variable="Aggregated Ocean Heat Content|Depth 1",
        region="World|Northern Hemisphere|Land",
        year=2093,
        # unit="10^22J"
    )

    assert_mdata_value(
        mdata,
        0,
        variable="Aggregated Ocean Heat Content|Depth 1",
        region="World|Southern Hemisphere|Land",
        year=1765,
        # unit="10^22J"
    )


def test_load_out_ocean_layers():
    mdata = MAGICCData(join(TEST_OUT_DIR, "TEMP_OCEANLAYERS.OUT"))

    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "2018-09-23 18:33"
    assert (
        mdata.metadata["magicc-version"]
        == "6.8.01 BETA, 7th July 2012 - live.magicc.org"
    )
    assert (
        "__MAGICC 6.X TEMP_OCEANLAYERS DATA OUTPUT FILE__" in mdata.metadata["header"]
    )
    assert (mdata["todo"] == "N/A").all()
    assert (mdata["unit"] == "K").all()

    assert_mdata_value(
        mdata,
        0,
        variable="Ocean Temperature|Layer 1",
        region="World",
        year=1765,
        unit="K",
    )

    assert_mdata_value(
        mdata,
        0.10679213,
        variable="Ocean Temperature|Layer 3",
        region="World",
        year=1973,
        unit="K",
    )

    assert_mdata_value(
        mdata,
        0.13890633,
        variable="Ocean Temperature|Layer 50",
        region="World",
        year=2100,
        unit="K",
    )


def test_load_out_ocean_layers_hemisphere():
    mdata = MAGICCData(join(TEST_OUT_DIR, "TEMP_OCEANLAYERS_NH.OUT"))

    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "2018-09-23 18:33"
    assert (
        mdata.metadata["magicc-version"]
        == "6.8.01 BETA, 7th July 2012 - live.magicc.org"
    )
    assert (
        "__MAGICC 6.X TEMP_OCEANLAYERS DATA OUTPUT FILE__" in mdata.metadata["header"]
    )
    assert (mdata["todo"] == "N/A").all()
    assert (mdata["unit"] == "K").all()

    assert_mdata_value(
        mdata,
        0,
        variable="Ocean Temperature|Layer 1",
        region="World|Northern Hemisphere|Ocean",
        year=1765,
        unit="K",
    )

    assert_mdata_value(
        mdata,
        0.10679213,
        variable="Ocean Temperature|Layer 3",
        region="World|Northern Hemisphere|Ocean",
        year=1973,
        unit="K",
    )

    assert_mdata_value(
        mdata,
        0.13890633,
        variable="Ocean Temperature|Layer 50",
        region="World|Northern Hemisphere|Ocean",
        year=2100,
        unit="K",
    )


def test_load_out_inverseemis():
    mdata = MAGICCData(join(TEST_OUT_DIR, "INVERSEEMIS.OUT"))

    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "2018-09-23 18:33"
    assert (
        mdata.metadata["magicc-version"]
        == "6.8.01 BETA, 7th July 2012 - live.magicc.org"
    )
    assert "__MAGICC 6.X MISC DATA OUTPUT FILE__" in mdata.metadata["header"]
    assert (mdata["todo"] == "N/A").all()
    assert (mdata["region"] == "World").all()

    assert_mdata_value(
        mdata,
        0.01369638,
        variable="Inverse Emissions|CO2|MAGICC Fossil and Industrial",
        region="World",
        year=1765,
        unit="Gt C / yr",
    )

    assert_mdata_value(
        mdata,
        2.6233208,
        variable="Inverse Emissions|N2O",
        region="World",
        year=1770,
        unit="Mt N2ON / yr",
    )

    assert_mdata_value(
        mdata,
        155.86567,
        variable="Inverse Emissions|CH3Br",
        region="World",
        year=2099,
        unit="kt CH3Br / yr",
    )

    assert_mdata_value(
        mdata,
        0.0,
        variable="Inverse Emissions|CH3Cl",
        region="World",
        year=2100,
        unit="kt CH3Cl / yr",
    )


def test_load_out_co2pf_emis():
    mdata = MAGICCData(join(TEST_OUT_DIR, "DAT_CO2PF_EMIS.OUT"))

    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "2018-09-23 18:33"
    assert (
        mdata.metadata["magicc-version"]
        == "6.8.01 BETA, 7th July 2012 - live.magicc.org"
    )
    assert "__MAGICC 6.X DATA OUTPUT FILE__" in mdata.metadata["header"]
    assert (mdata["todo"] == "N/A").all()
    assert (mdata["unit"] == "Gt C / yr").all()
    assert (mdata["variable"] == "Land to Air Flux|CO2|MAGICC Permafrost").all()

    assert_mdata_value(mdata, 0, region="World", year=1765)

    assert_mdata_value(mdata, 0, region="World|Northern Hemisphere|Land", year=1765)

    assert_mdata_value(mdata, 0, region="World|Northern Hemisphere|Ocean", year=1765)

    assert_mdata_value(mdata, 0, region="World|Southern Hemisphere|Land", year=1765)

    assert_mdata_value(mdata, 0, region="World|Southern Hemisphere|Ocean", year=1765)


def test_load_parameters_out_with_magicc_input():
    test_file = "PARAMETERS.OUT"
    expected_error_msg = (
        r"^"
        + re.escape(
            "MAGCCInput cannot read PARAMETERS.OUT as it is a config style file"
        )
        + re.escape(", please use pymagicc.io.read_cfg_file")
        + r"$"
    )

    with pytest.raises(ValueError, match=expected_error_msg):
        MAGICCData(join(TEST_OUT_DIR, test_file))


xfail_msg = (
    "Output config files have heaps of spurious spaces, need to decide what to do "
    "about this. If we strip them, we give the illustion that they're usable, "
    "which they're not really..."
)


@pytest.mark.xfail(reason=xfail_msg)
def test_load_parameters_out():
    cfg = read_cfg_file(join(TEST_OUT_DIR, "PARAMETERS.OUT"))

    assert cfg["NML_YEARS"]["STARTYEAR"] == 1765
    assert cfg["NML_YEARS"]["STEPSPERYEAR"] == 12

    assert cfg["NML_ALLCFGS"]["PATHNAME_OUTFILES"] == "../out/"
    assert cfg["NML_ALLCFGS"]["CO2_FEEDBACKFACTOR_GPP"] == 0.01070037

    assert cfg["NML_OUTPUTCFGS"]["RF_INTEFFICACY_CH4"] == 0.987766458278542
    assert cfg["NML_OUTPUTCFGS"]["RF_REGIONS_AER_DIR"] == [
        -0.819497642538182,
        -0.804446767198558,
        -0.02718573381799450,
        -0.01260873055223082,
    ]


def test_filter():
    mdata = MAGICCData(join(MAGICC6_DIR, "HISTRCP_CO2I_EMIS.IN"))

    tvariable = "Emissions|CO2|MAGICC Fossil and Industrial"
    tregion = "World|R5LAM"
    tyear = 1983
    result = mdata.filter(variable=tvariable, region=tregion).timeseries()
    mask = np.array(
        (mdata.meta["variable"] == tvariable) & (mdata.meta["region"] == tregion)
    )
    expected = mdata.timeseries()[mask]
    pd.testing.assert_frame_equal(result, expected, check_names=False, check_like=True)


def test_incomplete_filepath():
    with pytest.raises(FileNotFoundError):
        MAGICCData(join("/incomplete/dir/name"))

    with pytest.raises(FileNotFoundError):
        MAGICCData(join("RCP26.SCEN"))


def test_invalid_name():
    with pytest.raises(FileNotFoundError):
        MAGICCData(join("/tmp", "MYNONEXISTANT.IN"))


def test_header_metadata():
    m = _Reader("test")
    assert m.process_header("lkhdsljdkjflkjndlkjlkndjgf") == {}
    assert m.process_header("") == {}
    assert m.process_header("Data: Average emissions per year") == {
        "data": "Average emissions per year"
    }
    assert m.process_header(
        "DATA:  Historical landuse BC (BCB) Emissions (HISTRCP_BCB_EMIS) "
    ) == {"data": "Historical landuse BC (BCB) Emissions (HISTRCP_BCB_EMIS)"}
    assert m.process_header(
        "CONTACT:   RCP 3-PD (IMAGE): Detlef van Vuuren (detlef.vanvuuren@pbl.nl); RCP 4.5 (MiniCAM): Allison Thomson (Allison.Thomson@pnl.gov); RCP 6.0 (AIM): Toshihiko Masui (masui@nies.go.jp); RCP 8.5 (MESSAGE): Keywan Riahi (riahi@iiasa.ac.at); Base year emissions inventories: Steve Smith (ssmith@pnl.gov) and Jean-Francois Lamarque (Jean-Francois.Lamarque@noaa.gov) "
    ) == {
        "contact": "RCP 3-PD (IMAGE): Detlef van Vuuren (detlef.vanvuuren@pbl.nl); RCP 4.5 (MiniCAM): Allison Thomson (Allison.Thomson@pnl.gov); RCP 6.0 (AIM): Toshihiko Masui (masui@nies.go.jp); RCP 8.5 (MESSAGE): Keywan Riahi (riahi@iiasa.ac.at); Base year emissions inventories: Steve Smith (ssmith@pnl.gov) and Jean-Francois Lamarque (Jean-Francois.Lamarque@noaa.gov)"
    }

    assert m.process_header(
        "DATE: 26/11/2009 11:29:06; MAGICC-VERSION: 6.3.09, 25 November 2009"
    ) == {"date": "26/11/2009 11:29:06; MAGICC-VERSION: 6.3.09, 25 November 2009"}

    m = _Reader("test")
    assert m.process_header("lkhdsljdkjflkjndlkjlkndjgf") == {}
    assert m.process_header("") == {}
    assert m.process_header("Data: Average emissions per year\nother text") == {
        "data": "Average emissions per year"
    }
    assert m.process_header("           Data: Average emissions per year    ") == {
        "data": "Average emissions per year"
    }
    assert m.process_header(
        "Compiled by: Zebedee Nicholls, Australian-German Climate & Energy College"
    ) == {"compiled by": "Zebedee Nicholls, Australian-German Climate & Energy College"}


def test_magicc_input_init():
    # must init with data
    with pytest.raises(TypeError):
        mdata = MAGICCData()


def test_magicc_input_init_preserves_columns():
    tmodel = "test model"
    tscenario = "test scenario"
    tclimate_model = "test climate model"

    test_df = pd.DataFrame(
        {
            "model": tmodel,
            "scenario": tscenario,
            "climate_model": tclimate_model,
            "variable": "Surface Temperature",
            "region": "World|R5REF",
            "unit": "K",
            "time": 2012,
            "value": 0.9,
        },
        index=[0],
    )
    mdata = MAGICCData(test_df)

    assert (mdata["model"] == tmodel).all()
    assert (mdata["scenario"] == tscenario).all()
    assert (mdata["climate_model"] == tclimate_model).all()


def test_set_lines():
    reader = _Reader("test")
    with pytest.raises(FileNotFoundError):
        reader._set_lines()

    test_file = join(TEST_DATA_DIR, "HISTSSP_CO2I_EMIS.IN")
    assert isfile(test_file)

    reader = _Reader(test_file)
    reader._set_lines()
    with open(test_file, "r", encoding="utf-8", newline="\n") as f:
        assert reader.lines == f.readlines()


@pytest.mark.parametrize(
    "test_filepath, expected_variable",
    [
        ("/test/filename/paths/HISTABCD_CH4_CONC.IN", "CH4_CONC"),
        ("test/filename.OUT", None),
    ],
)
def test_conc_in_reader_get_variable_from_filepath(test_filepath, expected_variable):
    conc_reader = _ConcInReader(test_filepath)
    if expected_variable is None:
        expected_message = re.escape(
            "Cannot determine variable from filepath: {}".format(test_filepath)
        )
        with pytest.raises(ValueError, match=expected_message):
            conc_reader._get_variable_from_filepath()
    else:
        assert conc_reader._get_variable_from_filepath() == expected_variable


@pytest.mark.parametrize(
    "starting_fpath, starting_fname, confusing_metadata",
    [
        (MAGICC6_DIR, "HISTRCP_CO2I_EMIS.IN", False),
        (MAGICC6_DIR, "HISTRCP_N2OI_EMIS.IN", False),
        (MAGICC6_DIR, "MARLAND_CO2I_EMIS.IN", True),  # weird units handling
        (MAGICC6_DIR, "HISTRCP_CO2_CONC.IN", False),
        (MAGICC6_DIR, "HISTRCP_HFC245fa_CONC.IN", True),  # weird units handling
        (MAGICC6_DIR, "HISTRCP_HFC43-10_CONC.IN", True),  # weird units handling
        (TEST_DATA_DIR, "HISTSSP_CO2I_EMIS.IN", False),
        (MAGICC6_DIR, "MIXED_NOXI_OT.IN", True),  # weird units handling
        (MAGICC6_DIR, "GISS_BCB_RF.IN", True),  # weird units handling
        (MAGICC6_DIR, "HISTRCP_SOLAR_RF.IN", True),  # weird units handling
        (MAGICC6_DIR, "HIST_VOLCANIC_RF.MON", True),  # weird units handling
        (
            MAGICC6_DIR,
            "RCPODS_WMO2006_Emissions_A1.prn",
            True,
        ),  # weird units/gas handling
        (
            MAGICC6_DIR,
            "RCPODS_WMO2006_MixingRatios_A1.prn",
            True,
        ),  # weird units and notes handling
        (MAGICC6_DIR, "RCP26.SCEN", True),  # metadata all over the place
        (MAGICC6_DIR, "SRESA1B.SCEN", True),  # metadata all over the place
        (TEST_DATA_DIR, "TESTSCEN7.SCEN7", False),
    ],
)
def test_in_file_read_write_functionally_identical(
    starting_fpath, starting_fname, confusing_metadata, temp_dir
):
    mi_writer = MAGICCData(join(starting_fpath, starting_fname))
    mi_writer.write(join(temp_dir, starting_fname), magicc_version=6)

    mi_written = MAGICCData(join(temp_dir, starting_fname))
    mi_initial = MAGICCData(join(starting_fpath, starting_fname))

    if not starting_fname.endswith((".SCEN", ".prn")):
        nml_written = f90nml.read(join(temp_dir, starting_fname))
        nml_initial = f90nml.read(join(temp_dir, starting_fname))
        assert sorted(nml_written["thisfile_specifications"]) == sorted(
            nml_initial["thisfile_specifications"]
        )

    # TODO: work out how to test files with confusing metadata, the Writers
    #       should fix the metadata but how to test that this has been fixed
    #       as intended is the next step
    if not confusing_metadata:
        for key_written, value_written in mi_written.metadata.items():
            try:
                assert value_written.strip() == mi_initial.metadata[key_written].strip()
            except:
                assert value_written == mi_initial.metadata[key_written]

    # drop index as we don't care about it
    pd.testing.assert_frame_equal(mi_written.timeseries(), mi_initial.timeseries())


emissions_valid = [
    "CO2I",
    "CO2B",
    "CH4",
    "N2O",
    "SOX",
    "CO",
    "NMVOC",
    "NOX",
    "BC",
    "OC",
    "NH3",
    "CF4",
    "C2F6",
    "C6F14",
    "HFC23",
    "HFC32",
    "HFC4310",
    "HFC125",
    "HFC134A",
    "HFC143A",
    "HFC227EA",
    "HFC245FA",
    "SF6",
]
global_only = ["WORLD"]
sres_regions = ["WORLD", "OECD90", "REF", "ASIA", "ALM"]
rcp_regions = ["WORLD", "R5OECD", "R5REF", "R5ASIA", "R5MAF", "R5LAM"]
# the fact these are valid for SCEN files but not for other data files is
# unbelievably confusing
rcp_regions_plus_bunkers = [
    "WORLD",
    "R5OECD",
    "R5REF",
    "R5ASIA",
    "R5MAF",
    "R5LAM",
    "BUNKERS",
]


@pytest.mark.parametrize(
    "regions, emissions, expected",
    [
        (global_only, emissions_valid, 11),
        (sres_regions, emissions_valid, 21),
        (sres_regions[1:], emissions_valid, "unrecognised regions"),
        (sres_regions, emissions_valid[1:], "unrecognised emissions"),
        (rcp_regions, emissions_valid, 31),
        (rcp_regions_plus_bunkers, emissions_valid, 41),
    ],
)
def test_get_scen_special_code(regions, emissions, expected):
    if expected == "unrecognised regions":
        error_msg = re.escape(
            "Could not determine scen special code for regions {}".format(regions)
        )

        with pytest.raises(ValueError, match=error_msg):
            get_special_scen_code(regions, emissions)
    elif expected == "unrecognised emissions":
        error_msg = re.escape(
            "Could not determine scen special code for emissions {}".format(emissions)
        )

        with pytest.raises(ValueError, match=error_msg):
            get_special_scen_code(regions, emissions)
    else:
        result = get_special_scen_code(regions, emissions)
        assert result == expected


@pytest.mark.parametrize("file_to_read", [f for f in listdir(MAGICC6_DIR)])
def test_can_read_all_files_in_magicc6_in_dir(file_to_read):
    if file_to_read.endswith((".exe")):
        pass
    elif file_to_read.endswith(".CFG"):
        read_cfg_file(join(MAGICC6_DIR, file_to_read))
    else:
        mdata = MAGICCData(join(MAGICC6_DIR, file_to_read))
        # make sure that no emissions units are read in bare e.g. the units of BC
        # should be Mt BC / time, not simply Mt
        assert not mdata["unit"].isin(["kt", "Mt"]).any()


@pytest.mark.parametrize("file_to_read", [f for f in TEST_OUT_FILES])
def test_can_read_all_valid_files_in_magicc6_out_dir(file_to_read):
    if file_to_read.endswith(("PARAMETERS.OUT")):
        read_cfg_file(join(TEST_OUT_DIR, file_to_read))
    else:
        for p in INVALID_OUT_FILES:
            if re.match(p, file_to_read):
                return
        mdata = MAGICCData(join(TEST_OUT_DIR, file_to_read))
        # make sure that no emissions units are read in bare e.g. the units of BC
        # should be Mt BC / time, not simply Mt
        assert not mdata["unit"].isin(["kt", "Mt"]).any()


@pytest.mark.parametrize("file_to_read", [f for f in TEST_OUT_FILES])
def test_cant_read_all_invalid_files_in_magicc6_out_dir(file_to_read):
    valid_filepath = True
    for p in INVALID_OUT_FILES:
        if re.match(p, file_to_read):
            valid_filepath = False

    if valid_filepath:
        return

    if ("SUBANN" in file_to_read) or ("VOLCANIC_RF.BINOUT" in file_to_read):
        error_msg = (
            r"^.*"
            + re.escape(": Only annual binary files can currently be processed")
            + r".*$"
        )
        with pytest.raises(InvalidTemporalResError, match=error_msg):
            MAGICCData(join(TEST_OUT_DIR, file_to_read))
    else:
        error_msg = (
            r"^.*"
            + re.escape(
                "is in an odd format for which we will never provide a reader/writer"
            )
            + r".*$"
        )
        with pytest.raises(NoReaderWriterError, match=error_msg):
            MAGICCData(join(TEST_OUT_DIR, file_to_read))


@pytest.mark.parametrize(
    "file_to_read",
    [f for f in listdir(TEST_OUT_DIR) if f.endswith("BINOUT") and f.startswith("DAT_")],
)
def test_bin_and_ascii_equal(file_to_read):
    try:
        mdata_bin = MAGICCData(join(TEST_OUT_DIR, file_to_read))
    except InvalidTemporalResError:
        # Some BINOUT files are on a subannual time scale and cannot be read (yet)
        return

    assert (mdata_bin["unit"] == "unknown").all()
    assert (mdata_bin["todo"] == "SET").all()

    mdata_ascii = MAGICCData(join(TEST_OUT_DIR, file_to_read.replace("BINOUT", "OUT")))

    # There are some minor differences between in the dataframes due to availability
    # of metadata in BINOUT files
    drop_axes = ["unit", "todo"]
    pd.testing.assert_frame_equal(mdata_ascii._data, mdata_bin._data, check_like=False)
    pd.testing.assert_frame_equal(
        mdata_ascii.meta.drop(drop_axes, axis="columns"),
        mdata_bin.meta.drop(drop_axes, axis="columns"),
    )


@patch("pymagicc.io._read_and_return_metadata_df")
def test_magicc_data_append(mock_read_and_return_metadata_df):
    tfilepath = "mocked/out/here.txt"

    tindex_yr = 2000
    tmetadata_init = {"mock": 12, "mock 2": "written here"}
    tdf_init_df = pd.DataFrame([[2.0, 1.2, 7.9]], index=[tindex_yr])
    tdf_init_columns = {
        "model": ["a"],
        "scenario": ["b"],
        "climate_model": ["c"],
        "region": ["World|ASIA"],
        "variable": ["GE", "GE|Coal", "GE|Gas"],
        "unit": ["J/y"],
    }
    # TODO: refactor MAGICCData so it can be instantiated with timeseries
    # like ScmDataFrameBase
    tdf_init = tdf_init_df.T
    tdf_init.index = pd.MultiIndex.from_product(
        tdf_init_columns.values(), names=tdf_init_columns.keys()
    )

    tmetadata_append = {"mock 12": 7, "mock 24": "written here too"}
    tdf_append_df = pd.DataFrame([[-6.0, 3.2, 7.1]], index=[tindex_yr])
    tdf_append_columns = {
        "model": ["d"],
        "scenario": ["e"],
        "climate_model": ["f"],
        "region": ["World|ASIA"],
        "variable": ["GE", "GE|Coal", "GE|Gas"],
        "unit": ["J/y"],
    }
    tdf_append = tdf_append_df.T
    tdf_append.index = pd.MultiIndex.from_product(
        tdf_append_columns.values(), names=tdf_append_columns.keys()
    )

    mock_read_and_return_metadata_df.return_value = (
        tmetadata_init,
        tdf_init_df,
        tdf_init_columns,
    )
    mdata = MAGICCData("mocked")

    mock_read_and_return_metadata_df.return_value = (
        tmetadata_append,
        tdf_append_df,
        tdf_append_columns,
    )
    mdata.append(tfilepath)

    mock_read_and_return_metadata_df.assert_called_with(tfilepath)

    expected_metadata = deepcopy(tmetadata_init)
    expected_metadata.update(tmetadata_append)
    assert mdata.metadata == expected_metadata

    expected = pd.concat([tdf_init, tdf_append])
    expected.columns = pd.Index(
        [datetime.datetime(tindex_yr, 1, 1, 0, 0, 0)], dtype="object"
    )

    pd.testing.assert_frame_equal(
        mdata.timeseries(),
        expected.sort_index().reorder_levels(mdata.timeseries().index.names),
        check_like=True,
    )


@patch("pymagicc.io.pull_cfg_from_parameters_out")
@patch("pymagicc.io.read_cfg_file")
def test_pull_cfg_from_parameters_out_file(
    mock_read_cfg_file, mock_pull_cfg_from_parameters_out
):
    tfile = "here/there/PARAMETERS.OUT"
    tparas_out = {"nml_allcfgs": {"para_1": 3}}
    tnamelist_out = f90nml.Namelist(tparas_out)

    mock_read_cfg_file.return_value = tparas_out
    mock_pull_cfg_from_parameters_out.return_value = tnamelist_out

    result = pull_cfg_from_parameters_out_file(tfile)
    assert result == tnamelist_out
    mock_read_cfg_file.assert_called_with(tfile)
    mock_pull_cfg_from_parameters_out.assert_called_with(
        tparas_out, namelist_to_read="nml_allcfgs"
    )

    result = pull_cfg_from_parameters_out_file(tfile, namelist_to_read="nml_test")
    assert result == tnamelist_out
    mock_read_cfg_file.assert_called_with(tfile)
    mock_pull_cfg_from_parameters_out.assert_called_with(
        tparas_out, namelist_to_read="nml_test"
    )


def test_pull_cfg_from_parameters_out():
    tparas_out = {
        "nml_allcfgs": {
            "para_1": 3,
            "para_2": "  string  here  ",
            "para_2": [1, 2, 3, 4],
            "para_2": [" as sld  ", "abc", "\x00"],
            "file_tuningmodel": "MAGTUNE_ABC.CFG",
            "file_tuningmodel_2": "MAGTUNE_DEF.CFG",
            "file_tuningmodel_3": "MAGTUNE_JAKF.CFG",
        },
        "nml_outcfgs": {
            "para_1": -13,
            "para_2": "string  here too",
            "para_2": [-0.1, 0, 0.1, 0.2],
            "para_2": ["tabs sldx  ", "  abc  ", "\x00", "\x00", " "],
        },
    }

    result = pull_cfg_from_parameters_out(tparas_out)
    expected = f90nml.Namelist(
        {
            "nml_allcfgs": {
                "para_1": 3,
                "para_2": "string  here",
                "para_2": [1, 2, 3, 4],
                "para_2": ["as sld", "abc"],
                "file_tuningmodel": "",
                "file_tuningmodel_2": "",
                "file_tuningmodel_3": "",
            }
        }
    )
    for key, value in result.items():
        for sub_key, sub_value in value.items():
            assert sub_value == expected[key][sub_key]

    result = pull_cfg_from_parameters_out(
        f90nml.Namelist(tparas_out), namelist_to_read="nml_outcfgs"
    )
    expected = f90nml.Namelist(
        {
            "nml_outcfgs": {
                "para_1": -13,
                "para_2": "string  here too",
                "para_2": [-0.1, 0, 0.1, 0.2],
                "para_2": ["tabs sldx", "abc"],
            }
        }
    )
    for key, value in result.items():
        for sub_key, sub_value in value.items():
            assert sub_value == expected[key][sub_key]


# integration test
def test_join_timeseries():
    mdata = MAGICCData(join(TEST_DATA_DIR, "RCP3PD_EMISSIONS.DAT"))

    base = deepcopy(mdata)
    base["todo"] = "SET"

    scen = MAGICCData(join(MAGICC6_DIR, "RCP60.SCEN"))

    res = join_timeseries(base=base, overwrite=scen, join_linear=[2005, 2012])

    assert_mdata_value(
        res,
        6.735,
        variable="Emissions|CO2|MAGICC Fossil and Industrial",
        region="World",
        year=2000,
        unit="Gt C / yr",
        todo="SET",
    )

    val_2012 = 8.5115 + (8.9504 - 8.5115) * 2 / 10
    expected = 7.971 + (val_2012 - 7.971) / 7 * 3
    assert_mdata_value(
        res,
        expected,
        variable="Emissions|CO2|MAGICC Fossil and Industrial",
        region="World",
        year=2008,
        unit="Gt C / yr",
        todo="SET",
    )

    expected = 8.5115 + (8.9504 - 8.5115) / 2
    assert_mdata_value(
        res,
        expected,
        variable="Emissions|CO2|MAGICC Fossil and Industrial",
        region="World",
        year=2015,
        unit="Gt C / yr",
        todo="SET",
    )

    assert_mdata_value(
        res,
        119.235,
        variable="Emissions|CFC11",
        region="World",
        year=1995,
        unit="kt CFC11 / yr",
        todo="SET",
    )

    assert_mdata_value(
        res,
        36.338,
        variable="Emissions|CFC11",
        region="World",
        year=2015,
        unit="kt CFC11 / yr",
        todo="SET",
    )


@patch("pymagicc.io.MAGICCData")
@patch("pymagicc.io._join_timeseries_mdata")
@patch("pymagicc.io.isinstance")
def test_join_timeseries_unit(
    mock_isinstance, mock_join_timeseries_mdata, mock_magicc_data
):
    tbase = 13
    toverwrite = 14
    tdf = "mocked as well"
    toutput = "mocked output"

    mock_join_timeseries_mdata.return_value = toutput
    mock_isinstance.return_value = False

    res = join_timeseries(base=tbase, overwrite=toverwrite)

    assert res == mock_magicc_data.return_value

    mock_join_timeseries_mdata.assert_called_with(tbase, toverwrite, None)


@pytest.fixture(scope="function")
def join_base_df():
    bdf = pd.DataFrame(
        [
            [2000, "Emissions|CO2", "GtC/yr", "World", 1.0, "a", "b"],
            [2010, "Emissions|CO2", "GtC/yr", "World", 2.0, "a", "b"],
            [2020, "Emissions|CO2", "GtC/yr", "World", 3.0, "a", "b"],
            [2000, "Emissions|CH4", "MtCH4/yr", "World", 1.1, "a", "b"],
            [2010, "Emissions|CH4", "MtCH4/yr", "World", 1.2, "a", "b"],
            [2020, "Emissions|CH4", "MtCH4/yr", "World", 1.3, "a", "b"],
        ],
        columns=["time", "variable", "unit", "region", "value", "model", "scenario"],
    )

    yield MAGICCData(bdf)


@pytest.fixture(scope="function")
def join_overwrite_df():
    odf = pd.DataFrame(
        [
            [2015, "Emissions|CO2", "GtC/yr", "World", 1.0, "a", "b"],
            [2050, "Emissions|CO2", "GtC/yr", "World", 2.0, "a", "b"],
            [2100, "Emissions|CO2", "GtC/yr", "World", 3.0, "a", "b"],
        ],
        columns=["time", "variable", "unit", "region", "value", "model", "scenario"],
    )

    yield MAGICCData(odf)


def test_join_timeseries_mdata_no_harmonisation(join_base_df, join_overwrite_df):
    msg = (
        "There are nan values in joint arrays, this is likely because, once "
        "joined, your input timeseries do not all cover the same timespan."
    )
    with warnings.catch_warnings(record=True) as warn_result:
        res = MAGICCData(
            _join_timeseries_mdata(
                base=join_base_df, overwrite=join_overwrite_df, join_linear=None
            )
        )

    assert len(warn_result) == 1
    assert str(warn_result[0].message) == msg

    assert_mdata_value(
        res, 1.5, variable="Emissions|CO2", region="World", year=2005, unit="GtC/yr"
    )

    assert_mdata_value(
        res, 1, variable="Emissions|CO2", region="World", year=2015, unit="GtC/yr"
    )

    assert_mdata_value(
        res,
        1 + (2 - 1) / 35 * 5,
        variable="Emissions|CO2",
        region="World",
        year=2020,
        unit="GtC/yr",
    )

    assert_mdata_value(
        res, 1.3, variable="Emissions|CH4", region="World", year=2020, unit="MtCH4/yr"
    )

    assert (
        res.filter(variable="Emissions|CH4", region="World", year=2100, unit="MtCH4/yr")
        .timeseries()
        .empty
    )


def test_join_timeseries_mdata_harmonisation(join_base_df, join_overwrite_df):
    res = MAGICCData(
        _join_timeseries_mdata(
            base=join_base_df, overwrite=join_overwrite_df, join_linear=[2010, 2020]
        )
    )

    overwrite_co2_val_2020 = 1 + (2 - 1) / 35 * 5
    expected = 2 + (overwrite_co2_val_2020 - 2) / 10 * 2
    assert_mdata_value(
        res,
        expected,
        variable="Emissions|CO2",
        region="World",
        year=2012,
        unit="GtC/yr",
    )

    assert_mdata_value(
        res, 2, variable="Emissions|CO2", region="World", year=2050, unit="GtC/yr"
    )

    assert_mdata_value(
        res, 1.3, variable="Emissions|CH4", region="World", year=2020, unit="MtCH4/yr"
    )


def test_join_timeseries_mdata_harmonisation_errors(join_base_df, join_overwrite_df):
    error_msg = re.escape("join_linear start year is after end of base timeseries")
    with pytest.raises(ValueError, match=error_msg):
        join_timeseries(
            base=join_base_df, overwrite=join_overwrite_df, join_linear=[2025, 2030]
        )

    error_msg = re.escape(
        "join_linear end year is before start of overwrite timeseries"
    )
    with pytest.raises(ValueError, match=error_msg):
        join_timeseries(
            base=join_base_df, overwrite=join_overwrite_df, join_linear=[2005, 2010]
        )

    error_msg = re.escape("join_linear must have a length of 2")
    with pytest.raises(ValueError, match=error_msg):
        join_timeseries(
            base=join_base_df,
            overwrite=join_overwrite_df,
            join_linear=[2000, 2020, 2011],
        )

    join_base_df = join_base_df.filter(variable="Emissions|CH4")
    error_msg = re.escape("No overlapping indices, a simple append will do")
    with pytest.raises(ValueError, match=error_msg):
        join_timeseries(base=join_base_df, overwrite=join_overwrite_df)


@patch("pymagicc.io.MAGICCData")
@patch("pymagicc.io._join_timeseries_mdata")
def test_join_timeseries_filenames(mock_join_timeseries_mdata, mock_magicc_data):
    tbase = "string1"
    toverwrite = "string2"
    tmdata = 54
    treturn = 12

    mock_magicc_data.return_value = tmdata

    mock_join_timeseries_mdata.return_value = treturn

    res = join_timeseries(base=tbase, overwrite=toverwrite)

    assert res == mock_magicc_data.return_value

    assert mock_magicc_data.call_count == 3
    mock_join_timeseries_mdata.assert_called_with(tmdata, tmdata, None)


# TODO: improve join timeseries so it can also handle datetimes in the time axis


def test_write_emis_in_unrecognised_region_error(temp_dir, writing_base_emissions):
    tregions = ["R5REF", "R5OECD", "R5LAM", "R5ASIA", "R5MAF"]
    writing_base_emissions.set_meta(tregions, name="region")
    writing_base_emissions.set_meta("Emissions|CO2", name="variable")
    writing_base_emissions.metadata = {"header": "TODO: fix error message"}

    error_msg = re.escape(
        "Are all of your regions OpenSCM regions? I don't "
        "recognise: {}".format(sorted(tregions))
    )
    with pytest.raises(ValueError, match=error_msg):
        writing_base_emissions.write(
            join(temp_dir, "TMP_CO2_EMIS.IN"), magicc_version=6
        )


def test_write_unrecognised_region_combination_error(temp_dir, writing_base_emissions):
    writing_base_emissions.set_meta("Emissions|CO2", name="variable")
    error_msg = re.escape(
        "Unrecognised regions, they must be part of "
        "pymagicc.definitions.DATTYPE_REGIONMODE_REGIONS. If that doesn't make "
        "sense, please raise an issue at "
        "https://github.com/openclimatedata/pymagicc/issues"
    )
    assert isinstance(pymagicc.definitions.DATTYPE_REGIONMODE_REGIONS, pd.DataFrame)
    with pytest.raises(ValueError, match=error_msg):
        writing_base_emissions.write(
            join(temp_dir, "TMP_CO2_EMIS.IN"), magicc_version=6
        )


def test_write_no_header_error(temp_dir, writing_base_emissions):
    writing_base_emissions.set_meta("Emissions|CO2", name="variable")
    tregions = [
        "World|{}".format(r) for r in ["R5REF", "R5OECD", "R5LAM", "R5ASIA", "R5MAF"]
    ]
    writing_base_emissions.set_meta(tregions, name="region")
    writing_base_emissions.set_meta("Emissions|CO2", name="variable")
    writing_base_emissions.set_meta("GtC / yr", name="unit")

    error_msg = re.escape('Please provide a file header in ``self.metadata["header"]``')
    with pytest.raises(KeyError, match=error_msg):
        writing_base_emissions.write(
            join(temp_dir, "TMP_CO2_EMIS.IN"), magicc_version=6
        )


def run_writing_comparison(res, expected, update=False):
    """Run test that writing file is behaving as expected

    Parameters
    ----------
    res : str
        File written as part of the test

    expected : str
        File against which the comparison should be done

    update : bool
        If True, don't perform the test and instead simply
        overwrite the existing expected file with ``res``

    Raises
    ------
    AssertionError
        If ``update`` is ``False`` and ``res`` and ``expected``
        are not identical.
    """
    if update:
        shutil.copy(res, expected)
    else:
        assert filecmp.cmp(res, expected, shallow=False)


# integration test
def test_write_emis_in(temp_dir, update_expected_file, writing_base_emissions):
    tregions = [
        "World|{}".format(r) for r in ["R5REF", "R5OECD", "R5LAM", "R5ASIA", "R5MAF"]
    ]
    writing_base_emissions.set_meta(tregions, name="region")
    writing_base_emissions.set_meta("Emissions|CO2", name="variable")
    writing_base_emissions.set_meta("GtC / yr", name="unit")

    res = join(temp_dir, "TMP_CO2_EMIS.IN")
    writing_base_emissions.metadata = {"header": "Test CO2 Emissions file"}
    writing_base_emissions.write(res, magicc_version=6)

    expected = join(EXPECTED_FILES_DIR, "EXPECTED_CO2_EMIS.IN")

    run_writing_comparison(res, expected, update=update_expected_file)


def test_write_emis_in_variable_name_error(temp_dir, writing_base_emissions):
    tregions = [
        "World|{}".format(r) for r in ["R5REF", "R5OECD", "R5LAM", "R5ASIA", "R5MAF"]
    ]
    writing_base_emissions.set_meta(tregions, name="region")
    writing_base_emissions.set_meta("Emissions|CO2|MAGICC AFOLU", name="variable")
    writing_base_emissions.metadata = {"header": "Test misnamed CO2 Emissions file"}

    error_msg = re.escape(
        "Your filename variable, Emissions|CO2, does not match the data "
        "variable, Emissions|CO2|MAGICC AFOLU"
    )
    with pytest.raises(ValueError, match=error_msg):
        writing_base_emissions.write(
            join(temp_dir, "TMP_CO2_EMIS.IN"), magicc_version=6
        )


# integration test
def test_write_temp_in(temp_dir, update_expected_file, writing_base):
    # almost certain spacing doesn't matter for fourbox data, can always make more
    # restrictive in future if required
    tregions = [
        "World|{}|{}".format(r, sr)
        for r in ["Southern Hemisphere", "Northern Hemisphere"]
        for sr in ["Ocean", "Land"]
    ]
    writing_base.set_meta(tregions, name="region")
    writing_base.set_meta("Surface Temperature", name="variable")
    writing_base.set_meta("K", name="unit")

    res = join(temp_dir, "TMP_SURFACE_TEMP.IN")
    writing_base.metadata = {"header": "Test Surface temperature input file"}
    writing_base.write(res, magicc_version=6)

    expected = join(EXPECTED_FILES_DIR, "EXPECTED_SURFACE_TEMP.IN")

    run_writing_comparison(res, expected, update=update_expected_file)


def test_write_temp_in_variable_name_error(temp_dir, writing_base):
    tregions = [
        "World|{}|{}".format(r, sr)
        for r in ["Northern Hemisphere", "Southern Hemisphere"]
        for sr in ["Ocean", "Land"]
    ]
    writing_base.set_meta(tregions, name="region")
    writing_base.set_meta("Ocean Temperature", name="variable")
    writing_base.metadata = {"header": "Test misnamed Surface temperature file"}

    error_msg = re.escape(
        "Your filename variable, Surface Temperature, does not match the data "
        "variable, Ocean Temperature"
    )
    with pytest.raises(ValueError, match=error_msg):
        writing_base.write(join(temp_dir, "TMP_SURFACE_TEMP.IN"), magicc_version=6)


def test_surface_temp_in_reader():
    mdata = MAGICCData(join(EXPECTED_FILES_DIR, "EXPECTED_SURFACE_TEMP.IN"))

    generic_mdata_tests(mdata)

    assert "Test Surface temperature input file" in mdata.metadata["header"]
    assert (mdata["todo"] == "SET").all()
    assert (mdata["unit"] == "K").all()
    assert (mdata["variable"] == "Surface Temperature").all()

    assert_mdata_value(mdata, 6, region="World|Northern Hemisphere|Ocean", year=1996)

    assert_mdata_value(mdata, 3, region="World|Northern Hemisphere|Land", year=1995)

    assert_mdata_value(mdata, 4, region="World|Southern Hemisphere|Ocean", year=1996)

    assert_mdata_value(mdata, 5, region="World|Southern Hemisphere|Land", year=1996)
