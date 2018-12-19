from os import remove, listdir
from os.path import join, isfile, basename
from copy import deepcopy
import warnings
from unittest.mock import patch, MagicMock


import numpy as np
import pandas as pd
import re
import pytest
import f90nml


from pymagicc import MAGICC6
from pymagicc.io import (
    MAGICCData,
    _InputReader,
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
)
from .conftest import MAGICC6_DIR, TEST_DATA_DIR, TEST_OUT_DIR


# Not all files can be read in
TEST_OUT_FILES = listdir(TEST_OUT_DIR)

INVALID_OUT_FILES = [
    r"CARBONCYCLE.*OUT",
    r".*SUBANN.*BINOUT",
    r"DAT_VOLCANIC_RF\.BINOUT",
    r"PF.*OUT",
    r"DATBASKET_.*",
    r".*INVERSE.*EMIS.*OUT",
    r"PRECIPINPUT.*OUT",
    r"TEMP_OCEANLAYERS.*\.BINOUT",
    r"TIMESERIESMIX.*OUT",
    r"SUMMARY_INDICATORS.OUT",
]


def test_cant_find_reader_writer():
    mdata = MAGICCData()
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
        mdata.read(join(TEST_DATA_DIR, test_name))

    expected_message = expected_message.replace("reader", "writer")
    with pytest.raises(NoReaderWriterError, match=expected_message):
        mdata.write(test_name, magicc_version=6)


def test_get_invalid_tool():
    mdata = MAGICCData()
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
        mdata.determine_tool("EXAMPLE.SCEN", junk_tool)


def generic_mdata_tests(mdata):
    "Resusable tests to ensure data format."
    assert mdata.is_loaded == True

    assert isinstance(mdata.df, pd.DataFrame)
    pd.testing.assert_index_equal(
        mdata.df.columns,
        pd.Index(["variable", "todo", "unit", "region", "time", "value"]),
    )

    assert mdata.df.variable.dtype == "object"
    assert mdata.df.todo.dtype == "object"
    assert mdata.df.unit.dtype == "object"
    assert mdata.df.region.dtype == "object"

    for key in ["units", "unit", "firstdatarow", "dattype"]:
        with pytest.raises(KeyError):
            mdata.metadata[key]
    assert isinstance(mdata.metadata["header"], str)


def test_load_magicc6_emis():
    mdata = MAGICCData()
    assert mdata.is_loaded == False
    mdata.read(join(MAGICC6_DIR, "HISTRCP_CO2I_EMIS.IN"))
    generic_mdata_tests(mdata)

    row = (
        (mdata.df["variable"] == "Emissions|CO2|MAGICC Fossil and Industrial")
        & (mdata.df["region"] == "World|R5ASIA")
        & (mdata.df["time"] == 2000)
        & (mdata.df["unit"] == "Gt C / yr")
        & (mdata.df["todo"] == "SET")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 1.7682027e000)


def test_load_magicc6_emis_hyphen_in_units():
    mdata = MAGICCData()
    assert mdata.is_loaded == False
    mdata.read(join(MAGICC6_DIR, "HISTRCP_N2OI_EMIS.IN"))
    generic_mdata_tests(mdata)

    row = (
        (mdata.df["variable"] == "Emissions|N2O|MAGICC Fossil and Industrial")
        & (mdata.df["region"] == "World|R5ASIA")
        & (mdata.df["time"] == 2000)
        & (mdata.df["unit"] == "Mt N2ON / yr")
        & (mdata.df["todo"] == "SET")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.288028519)


def test_load_magicc5_emis():
    mdata = MAGICCData()
    assert mdata.is_loaded == False
    mdata.read(join(MAGICC6_DIR, "MARLAND_CO2I_EMIS.IN"))
    generic_mdata_tests(mdata)

    row = (
        (mdata.df["variable"] == "Emissions|CO2|MAGICC Fossil and Industrial")
        & (mdata.df["region"] == "World|Northern Hemisphere")
        & (mdata.df["time"] == 2000)
        & (mdata.df["unit"] == "Gt C / yr")
        & (mdata.df["todo"] == "SET")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value.values, 6.20403698)

    row = (
        (mdata.df["variable"] == "Emissions|CO2|MAGICC Fossil and Industrial")
        & (mdata.df["region"] == "World|Southern Hemisphere")
        & (mdata.df["time"] == 2002)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value.values, 0.495812385)

    row = (
        (mdata.df["variable"] == "Emissions|CO2|MAGICC Fossil and Industrial")
        & (mdata.df["region"] == "World|Southern Hemisphere")
        & (mdata.df["time"] == 1751)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value.values, 0.0)


def test_load_magicc5_emis_not_renamed_error():
    mdata = MAGICCData()

    test_path = TEST_DATA_DIR
    test_name = "MARLAND_CO2_EMIS_FOSSIL&IND.IN"

    expected_error_msg = re.escape(
        "Cannot determine variable from filepath: {}".format(join(test_path, test_name))
    )
    with pytest.raises(ValueError, match=expected_error_msg):
        mdata.read(join(test_path, test_name))


def test_load_magicc6_conc():
    mdata = MAGICCData()
    mdata.read(join(MAGICC6_DIR, "HISTRCP_CO2_CONC.IN"))

    assert (mdata.df.unit == "ppm").all()
    generic_mdata_tests(mdata)
    row = (
        (mdata.df["variable"] == "Atmospheric Concentrations|CO2")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1048)
        & (mdata.df["unit"] == "ppm")
        & (mdata.df["todo"] == "SET")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 2.80435733e002)


def test_load_magicc6_conc_old_style_name_umlaut_metadata():
    mdata = MAGICCData()
    mdata.read(join(MAGICC6_DIR, "HISTRCP_HFC245fa_CONC.IN"))

    assert (mdata.df.unit == "ppt").all()
    assert mdata.metadata["data"] == "Global average mixing ratio"
    generic_mdata_tests(mdata)
    rows = (
        (mdata.df["variable"] == "Atmospheric Concentrations|HFC245fa")
        & (mdata.df["region"] == "World")
        & (mdata.df["unit"] == "ppt")
        & (mdata.df["todo"] == "SET")
    )
    assert sum(rows) != 0
    np.testing.assert_allclose(mdata.df[rows].value, 0.0)


def test_load_magicc6_conc_old_style_name_with_hyphen():
    mdata = MAGICCData()
    mdata.read(join(MAGICC6_DIR, "HISTRCP_HFC43-10_CONC.IN"))

    assert (mdata.df.unit == "ppt").all()
    generic_mdata_tests(mdata)
    rows = (
        (mdata.df["variable"] == "Atmospheric Concentrations|HFC4310")
        & (mdata.df["region"] == "World")
        & (mdata.df["unit"] == "ppt")
        & (mdata.df["todo"] == "SET")
    )
    assert sum(rows) != 0
    np.testing.assert_allclose(mdata.df[rows].value, 0.0)


def test_load_magicc7_emis_umlaut_metadata():
    mdata = MAGICCData()
    mdata.read(join(TEST_DATA_DIR, "HISTSSP_CO2I_EMIS.IN"))

    generic_mdata_tests(mdata)

    assert (
        mdata.metadata["contact"]
        == "Zebedee Nicholls, Australian-German Climate and Energy College, University of Melbourne, zebedee.nicholls@climate-energy-college.org"
    )
    assert mdata.metadata["description"] == "Test line by näme with ümlauts ëh ça"
    assert (mdata.df.unit == "Gt C / yr").all()

    row = (
        (mdata.df["variable"] == "Emissions|CO2|MAGICC Fossil and Industrial")
        & (mdata.df["region"] == "World|R6REF")
        & (mdata.df["time"] == 2013)
        & (mdata.df["todo"] == "SET")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.6638)

    row = (
        (mdata.df["variable"] == "Emissions|CO2|MAGICC Fossil and Industrial")
        & (mdata.df["region"] == "World|R6ASIA")
        & (mdata.df["time"] == 2000)
        & (mdata.df["todo"] == "SET")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 1.6911)


def test_load_ot():
    mdata = MAGICCData()
    mdata.read(join(MAGICC6_DIR, "MIXED_NOXI_OT.IN"))

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

    assert (mdata.df.unit == "dimensionless").all()
    assert (mdata.df.todo == "SET").all()
    assert (
        mdata.df.variable == "Optical Thickness|NOx|MAGICC Fossil and Industrial"
    ).all()

    row = (
        (mdata.df["variable"] == "Optical Thickness|NOx|MAGICC Fossil and Industrial")
        & (mdata.df["region"] == "World|Northern Hemisphere|Ocean")
        & (mdata.df["time"] == 1765)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.00668115649)

    row = (
        (mdata.df["variable"] == "Optical Thickness|NOx|MAGICC Fossil and Industrial")
        & (mdata.df["region"] == "World|Northern Hemisphere|Ocean")
        & (mdata.df["time"] == 1765)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.00668115649)

    row = (
        (mdata.df["variable"] == "Optical Thickness|NOx|MAGICC Fossil and Industrial")
        & (mdata.df["region"] == "World|Northern Hemisphere|Land")
        & (mdata.df["time"] == 1865)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.526135104)

    row = (
        (mdata.df["variable"] == "Optical Thickness|NOx|MAGICC Fossil and Industrial")
        & (mdata.df["region"] == "World|Southern Hemisphere|Ocean")
        & (mdata.df["time"] == 1965)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.612718845)

    row = (
        (mdata.df["variable"] == "Optical Thickness|NOx|MAGICC Fossil and Industrial")
        & (mdata.df["region"] == "World|Southern Hemisphere|Land")
        & (mdata.df["time"] == 2000)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 3.70378)


def test_load_rf():
    mdata = MAGICCData()
    mdata.read(join(MAGICC6_DIR, "GISS_BCB_RF.IN"))

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

    assert (mdata.df.unit == "W / m^2").all()
    assert (mdata.df.todo == "SET").all()
    assert (mdata.df.variable == "Radiative Forcing|BC|MAGICC AFOLU").all()

    row = (
        (mdata.df["variable"] == "Radiative Forcing|BC|MAGICC AFOLU")
        & (mdata.df["region"] == "World|Northern Hemisphere|Ocean")
        & (mdata.df["time"] == 1765)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|BC|MAGICC AFOLU")
        & (mdata.df["region"] == "World|Northern Hemisphere|Land")
        & (mdata.df["time"] == 1865)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.268436597)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|BC|MAGICC AFOLU")
        & (mdata.df["region"] == "World|Southern Hemisphere|Ocean")
        & (mdata.df["time"] == 1965)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.443357552)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|BC|MAGICC AFOLU")
        & (mdata.df["region"] == "World|Southern Hemisphere|Land")
        & (mdata.df["time"] == 2000)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 1.53987244)


def test_load_solar_rf():
    mdata = MAGICCData()
    mdata.read(join(MAGICC6_DIR, "HISTRCP6SCP6to45_SOLAR_RF.IN"))

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

    assert (mdata.df.unit == "W / m^2").all()
    assert (mdata.todo == "SET").all()
    assert (mdata.df.variable == "Radiative Forcing|Solar").all()
    assert (mdata.df.region == "World").all()

    row = (mdata.df["variable"] == "Radiative Forcing|Solar") & (
        mdata.df["time"] == 1610
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0149792391)

    row = (mdata.df["variable"] == "Radiative Forcing|Solar") & (
        mdata.df["time"] == 1865
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, -0.00160201087)

    row = (mdata.df["variable"] == "Radiative Forcing|Solar") & (
        mdata.df["time"] == 1965
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0652917391)

    row = (mdata.df["variable"] == "Radiative Forcing|Solar") & (
        mdata.df["time"] == 2183
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0446329891)

    row = (mdata.df["variable"] == "Radiative Forcing|Solar") & (
        mdata.df["time"] == 2600
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.121325148)


def test_load_volcanic_rf():
    mdata = MAGICCData()
    mdata.read(join(MAGICC6_DIR, "HIST_VOLCANIC_RF.MON"))

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

    assert (mdata.df.unit == "W / m^2").all()
    assert (mdata.df.todo == "SET").all()
    assert (mdata.df.variable == "Radiative Forcing|Volcanic").all()

    # TODO: sort out time read in, maybe that's a step in openscm instead...
    row = (
        (mdata.df["variable"] == "Radiative Forcing|Volcanic")
        & (mdata.df["region"] == "World|Northern Hemisphere|Land")
        & (mdata.df["time"] == 1000.042)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|Volcanic")
        & (mdata.df["region"] == "World|Northern Hemisphere|Land")
        & (mdata.df["time"] == 1002.542)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, -0.0187500000)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|Volcanic")
        & (mdata.df["region"] == "World|Northern Hemisphere|Ocean")
        & (mdata.df["time"] == 1013.208)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|Volcanic")
        & (mdata.df["region"] == "World|Southern Hemisphere|Ocean")
        & (mdata.df["time"] == 1119.292)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, -0.222916667)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|Volcanic")
        & (mdata.df["region"] == "World|Southern Hemisphere|Land")
        & (mdata.df["time"] == 2006.958)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0)


def test_load_scen():
    mdata = MAGICCData()
    mdata.read(join(MAGICC6_DIR, "RCP26.SCEN"))

    generic_mdata_tests(mdata)

    assert (
        mdata.metadata["date"]
        == "26/11/2009 11:29:06; MAGICC-VERSION: 6.3.09, 25 November 2009"
    )
    assert "Final RCP3PD with constant emissions" in mdata.metadata["header"]

    row = (
        (mdata.df["variable"] == "Emissions|CO2|MAGICC Fossil and Industrial")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2000)
        & (mdata.df["unit"] == "Gt C / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 6.7350)

    row = (
        (mdata.df["variable"] == "Emissions|N2O")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2002)
        & (mdata.df["unit"] == "Mt N2ON / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 7.5487)

    row = (
        (mdata.df["variable"] == "Emissions|HFC4310")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2001)
        & (mdata.df["unit"] == "kt HFC4310 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.6470)

    row = (
        (mdata.df["variable"] == "Emissions|SOx")
        & (mdata.df["region"] == "World|R5OECD")
        & (mdata.df["time"] == 2005)
        & (mdata.df["unit"] == "Mt S / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 11.9769)

    row = (
        (mdata.df["variable"] == "Emissions|NMVOC")
        & (mdata.df["region"] == "World|R5OECD")
        & (mdata.df["time"] == 2050)
        & (mdata.df["unit"] == "Mt NMVOC / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 18.2123)

    row = (
        (mdata.df["variable"] == "Emissions|HFC23")
        & (mdata.df["region"] == "World|R5REF")
        & (mdata.df["time"] == 2100)
        & (mdata.df["unit"] == "kt HFC23 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0)

    row = (
        (mdata.df["variable"] == "Emissions|HFC143a")
        & (mdata.df["region"] == "World|R5ASIA")
        & (mdata.df["time"] == 2040)
        & (mdata.df["unit"] == "kt HFC143a / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 33.3635)

    row = (
        (mdata.df["variable"] == "Emissions|SF6")
        & (mdata.df["region"] == "World|R5ASIA")
        & (mdata.df["time"] == 2040)
        & (mdata.df["unit"] == "kt SF6 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.8246)

    row = (
        (mdata.df["variable"] == "Emissions|CO2|MAGICC AFOLU")
        & (mdata.df["region"] == "World|R5MAF")
        & (mdata.df["time"] == 2050)
        & (mdata.df["unit"] == "Gt C / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, -0.0125)

    row = (
        (mdata.df["variable"] == "Emissions|CH4")
        & (mdata.df["region"] == "World|R5MAF")
        & (mdata.df["time"] == 2070)
        & (mdata.df["unit"] == "Mt CH4 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 37.6218)

    row = (
        (mdata.df["variable"] == "Emissions|NOx")
        & (mdata.df["region"] == "World|R5LAM")
        & (mdata.df["time"] == 2080)
        & (mdata.df["unit"] == "Mt N / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 1.8693)

    row = (
        (mdata.df["variable"] == "Emissions|BC")
        & (mdata.df["region"] == "World|R5LAM")
        & (mdata.df["time"] == 2090)
        & (mdata.df["unit"] == "Mt BC / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.4254)

    row = (
        (mdata.df["variable"] == "Emissions|NH3")
        & (mdata.df["region"] == "World|Bunkers")
        & (mdata.df["time"] == 2000)
        & (mdata.df["unit"] == "Mt N / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0)

    row = (
        (mdata.df["variable"] == "Emissions|SF6")
        & (mdata.df["region"] == "World|Bunkers")
        & (mdata.df["time"] == 2002)
        & (mdata.df["unit"] == "kt SF6 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0)

    row = (
        (mdata.df["variable"] == "Emissions|HFC125")
        & (mdata.df["region"] == "World|R5REF")
        & (mdata.df["time"] == 2125)
        & (mdata.df["unit"] == "kt HFC125 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 5.2133)


def test_load_scen_year_first_column():
    mdata = MAGICCData()
    mdata.read(join(TEST_DATA_DIR, "RCP26_WORLD_ONLY_YEAR_FIRST_COLUMN.SCEN"))

    generic_mdata_tests(mdata)

    assert "Generic text" in mdata.metadata["header"]

    row = (
        (mdata.df["variable"] == "Emissions|CO2|MAGICC Fossil and Industrial")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2000)
        & (mdata.df["unit"] == "Gt C / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 6.7350)

    row = (
        (mdata.df["variable"] == "Emissions|N2O")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2002)
        & (mdata.df["unit"] == "Mt N2ON / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 7.5487)

    row = (
        (mdata.df["variable"] == "Emissions|HFC4310")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2001)
        & (mdata.df["unit"] == "kt HFC4310 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.6470)


@patch("pymagicc.io._ScenReader._read_data_header_line")
def test_load_scen_last_resort_message(mock_scen_header_line_reader):
    mock_scen_header_line_reader.side_effect = AssertionError

    mdata = MAGICCData()

    error_msg = re.escape(
        "This is unexpected, please raise an issue on "
        "https://github.com/openclimatedata/pymagicc/issues"
    )
    with pytest.raises(Exception, match=error_msg):
        mdata.read(join(MAGICC6_DIR, "RCP26.SCEN"))


def test_load_scen_sres():
    mdata = MAGICCData()
    mdata.read(join(MAGICC6_DIR, "SRESA1B.SCEN"))

    generic_mdata_tests(mdata)

    assert "Antero Hot Springs" in mdata.metadata["header"]

    row = (
        (mdata.df["variable"] == "Emissions|CO2|MAGICC Fossil and Industrial")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2000)
        & (mdata.df["unit"] == "Gt C / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 6.8963)

    row = (
        (mdata.df["variable"] == "Emissions|N2O")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1990)
        & (mdata.df["unit"] == "Mt N2ON / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 6.6751)

    row = (
        (mdata.df["variable"] == "Emissions|HFC4310")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2000)
        & (mdata.df["unit"] == "kt HFC4310 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0000)

    row = (
        (mdata.df["variable"] == "Emissions|SOx")
        & (mdata.df["region"] == "World|OECD90")
        & (mdata.df["time"] == 2010)
        & (mdata.df["unit"] == "Mt S / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 9.8762)

    row = (
        (mdata.df["variable"] == "Emissions|NMVOC")
        & (mdata.df["region"] == "World|OECD90")
        & (mdata.df["time"] == 2050)
        & (mdata.df["unit"] == "Mt NMVOC / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 28.1940)

    row = (
        (mdata.df["variable"] == "Emissions|HFC23")
        & (mdata.df["region"] == "World|REF")
        & (mdata.df["time"] == 2100)
        & (mdata.df["unit"] == "kt HFC23 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0624)

    row = (
        (mdata.df["variable"] == "Emissions|HFC125")
        & (mdata.df["region"] == "World|REF")
        & (mdata.df["time"] == 2100)
        & (mdata.df["unit"] == "kt HFC125 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 5.4067)

    row = (
        (mdata.df["variable"] == "Emissions|HFC143a")
        & (mdata.df["region"] == "World|ASIA")
        & (mdata.df["time"] == 2040)
        & (mdata.df["unit"] == "kt HFC143a / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 15.4296)

    row = (
        (mdata.df["variable"] == "Emissions|SF6")
        & (mdata.df["region"] == "World|ASIA")
        & (mdata.df["time"] == 2040)
        & (mdata.df["unit"] == "kt SF6 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 6.4001)

    row = (
        (mdata.df["variable"] == "Emissions|CO2|MAGICC AFOLU")
        & (mdata.df["region"] == "World|ALM")
        & (mdata.df["time"] == 2050)
        & (mdata.df["unit"] == "Gt C / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.2613)

    row = (
        (mdata.df["variable"] == "Emissions|CH4")
        & (mdata.df["region"] == "World|ALM")
        & (mdata.df["time"] == 2070)
        & (mdata.df["unit"] == "Mt CH4 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 130.1256)


def test_load_scen7():
    mdata = MAGICCData()
    mdata.read(join(TEST_DATA_DIR, "TESTSCEN7.SCEN7"))

    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "13-Oct-2017 16:45:35"
    assert mdata.metadata["description"] == "TEST SCEN7 file"
    assert "NOTES" in mdata.metadata["header"]
    assert "~~~~~" in mdata.metadata["header"]
    assert "Some notes" in mdata.metadata["header"]

    row = (
        (mdata.df["variable"] == "Emissions|CO2|MAGICC Fossil and Industrial")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2000)
        & (mdata.df["unit"] == "Gt C / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 6.7350)

    row = (
        (mdata.df["variable"] == "Emissions|N2O|MAGICC Fossil and Industrial")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2002)
        & (mdata.df["unit"] == "Mt N2ON / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 7.5487)

    row = (
        (mdata.df["variable"] == "Emissions|HFC23")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2001)
        & (mdata.df["unit"] == "kt HFC23 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 10.4328)

    row = (
        (mdata.df["variable"] == "Emissions|SOx")
        & (mdata.df["region"] == "World|R6OECD90")
        & (mdata.df["time"] == 2005)
        & (mdata.df["unit"] == "Mt S / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 11.9769)

    row = (
        (mdata.df["variable"] == "Emissions|NMVOC")
        & (mdata.df["region"] == "World|R6OECD90")
        & (mdata.df["time"] == 2050)
        & (mdata.df["unit"] == "Mt NMVOC / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 18.2123)

    row = (
        (mdata.df["variable"] == "Emissions|HFC23")
        & (mdata.df["region"] == "World|R6REF")
        & (mdata.df["time"] == 2100)
        & (mdata.df["unit"] == "kt HFC23 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0)

    row = (
        (mdata.df["variable"] == "Emissions|CH2Cl2")
        & (mdata.df["region"] == "World|R6REF")
        & (mdata.df["time"] == 2125)
        & (mdata.df["unit"] == "kt CH2Cl2 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 5.2133)

    row = (
        (mdata.df["variable"] == "Emissions|HFC143a")
        & (mdata.df["region"] == "World|R6ASIA")
        & (mdata.df["time"] == 2040)
        & (mdata.df["unit"] == "kt HFC143a / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 33.3635)

    row = (
        (mdata.df["variable"] == "Emissions|SO2F2")
        & (mdata.df["region"] == "World|R6ASIA")
        & (mdata.df["time"] == 2040)
        & (mdata.df["unit"] == "kt SO2F2 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.8246)

    row = (
        (mdata.df["variable"] == "Emissions|CO2|MAGICC AFOLU")
        & (mdata.df["region"] == "World|R6MAF")
        & (mdata.df["time"] == 2050)
        & (mdata.df["unit"] == "Gt C / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, -0.0125)

    row = (
        (mdata.df["variable"] == "Emissions|CH4")
        & (mdata.df["region"] == "World|R6MAF")
        & (mdata.df["time"] == 2070)
        & (mdata.df["unit"] == "Mt CH4 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 37.6218)

    row = (
        (mdata.df["variable"] == "Emissions|NOx")
        & (mdata.df["region"] == "World|R6LAM")
        & (mdata.df["time"] == 2080)
        & (mdata.df["unit"] == "Mt N / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 1.8693)

    row = (
        (mdata.df["variable"] == "Emissions|BC|MAGICC AFOLU")
        & (mdata.df["region"] == "World|R6LAM")
        & (mdata.df["time"] == 2090)
        & (mdata.df["unit"] == "Mt BC / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.4254)

    row = (
        (mdata.df["variable"] == "Emissions|NH3")
        & (mdata.df["region"] == "World|Bunkers")
        & (mdata.df["time"] == 2000)
        & (mdata.df["unit"] == "Mt N / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0)

    row = (
        (mdata.df["variable"] == "Emissions|SO2F2")
        & (mdata.df["region"] == "World|Bunkers")
        & (mdata.df["time"] == 2002)
        & (mdata.df["unit"] == "kt SO2F2 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0)


def test_load_scen7_mhalo():
    mdata = MAGICCData()
    mdata.read(join(TEST_DATA_DIR, "TEST_MHALO.SCEN7"))

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

    row = (
        (mdata.df["variable"] == "Emissions|CFC11")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2015)
        & (mdata.df["unit"] == "kt CFC11 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.343277)

    row = (
        (mdata.df["variable"] == "Emissions|CH3Br")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2065)
        & (mdata.df["unit"] == "kt CH3Br / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.925486)

    row = (
        (mdata.df["variable"] == "Emissions|Halon1301")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2100)
        & (mdata.df["unit"] == "kt Halon1301 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.047699, rtol=1e-4)


def test_load_prn():
    mdata = MAGICCData()
    mdata.read(join(MAGICC6_DIR, "RCPODS_WMO2006_Emissions_A1.prn"))

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
    assert (mdata.df.region == "World").all()
    assert (mdata.df.todo == "SET").all()
    assert not (mdata.df.unit == "t / yr").all()

    row = (
        (mdata.df["variable"] == "Emissions|CFC11")
        & (mdata.df["time"] == 1850)
        & (mdata.df["unit"] == "t CFC11 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0)

    row = (
        (mdata.df["variable"] == "Emissions|CFC115")
        & (mdata.df["time"] == 1965)
        & (mdata.df["unit"] == "t CFC115 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 444)

    row = (
        (mdata.df["variable"] == "Emissions|Halon1211")
        & (mdata.df["time"] == 1996)
        & (mdata.df["unit"] == "t Halon1211 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 10743)

    row = (
        (mdata.df["variable"] == "Emissions|Halon1301")
        & (mdata.df["time"] == 2017)
        & (mdata.df["unit"] == "t Halon1301 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 1062)

    row = (
        (mdata.df["variable"] == "Emissions|CH3Cl")
        & (mdata.df["time"] == 2500)
        & (mdata.df["unit"] == "t CH3Cl / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 3511082)


def test_load_prn_no_units():
    mdata = MAGICCData()
    mdata.read(join(MAGICC6_DIR, "WMO2006_ODS_A1Baseline.prn"))

    generic_mdata_tests(mdata)

    # top line should be ignored
    assert "6      1950      2100" not in mdata.metadata["header"]
    assert (
        "6/19/2006A1: Baseline emission file generated by John Daniel and Guus Velders"
        in mdata.metadata["header"]
    )

    assert (mdata.df.region == "World").all()
    assert (mdata.df.todo == "SET").all()
    assert not (mdata.df.unit == "t / yr").all()

    row = (
        (mdata.df["variable"] == "Emissions|CFC12")
        & (mdata.df["time"] == 1950)
        & (mdata.df["unit"] == "t CFC12 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 139965)

    row = (
        (mdata.df["variable"] == "Emissions|CH3Cl")
        & (mdata.df["time"] == 2100)
        & (mdata.df["unit"] == "t CH3Cl / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 3511082)


def test_load_prn_mixing_ratios_years_label():
    mdata = MAGICCData()
    mdata.read(join(MAGICC6_DIR, "RCPODS_WMO2006_MixingRatios_A1.prn"))

    generic_mdata_tests(mdata)

    # top line should be ignored
    assert "17      1850      2100" not in mdata.metadata["header"]
    assert mdata.metadata["data"] == "Global average mixing ratios"
    assert (
        mdata.metadata["description"]
        == "1951-2100 Baseline mixing ratio file generated by John Daniel and Guus Velders for WMO2006, Chapter 8. (2/3/06); CH3CL updated to reflect MAGICC6 timeseries after 1955 and lower 2000 concentrations closer to 535ppt in line with"
    )
    assert (mdata.df.region == "World").all()
    assert (mdata.df.todo == "SET").all()
    assert (mdata.df.unit == "ppt").all()

    row = (mdata.df["variable"] == "Atmospheric Concentrations|CFC12") & (
        mdata.df["time"] == 1850
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0)

    row = (mdata.df["variable"] == "Atmospheric Concentrations|CFC114") & (
        mdata.df["time"] == 1965
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 5.058)

    row = (mdata.df["variable"] == "Atmospheric Concentrations|HCFC141b") & (
        mdata.df["time"] == 2059
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 13.81)

    row = (mdata.df["variable"] == "Atmospheric Concentrations|Halon2402") & (
        mdata.df["time"] == 2091
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.007)

    row = (mdata.df["variable"] == "Atmospheric Concentrations|CH3Cl") & (
        mdata.df["time"] == 2100
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 538)


def test_load_rcp_historical_dat_emissions():
    mdata = MAGICCData()
    test_file = "20THCENTURY_EMISSIONS.DAT"
    mdata.read(join(TEST_DATA_DIR, test_file))
    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "26/11/2009 11:29:06"
    assert mdata.metadata["magicc-version"] == "6.3.09, 25 November 2009"
    assert "PRE2005__EMISSIONS" in mdata.metadata["header"]
    assert (
        "COLUMN_DESCRIPTION________________________________________"
        in mdata.metadata["header"]
    )

    assert (mdata.df["variable"].str.startswith("Emissions|")).all()
    assert (mdata.df["region"] == "World").all()
    assert (mdata.df["todo"] == "SET").all()

    row = (
        (mdata.df["variable"] == "Emissions|CO2|MAGICC Fossil and Industrial")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1766)
        & (mdata.df["unit"] == "Gt C / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.003)

    row = (
        (mdata.df["variable"] == "Emissions|CH4")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1767)
        & (mdata.df["unit"] == "Mt CH4 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 2.4364481)

    row = (
        (mdata.df["variable"] == "Emissions|CH3Cl")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2005)
        & (mdata.df["unit"] == "kt CH3Cl / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 3511.0820)


def test_load_rcp_historical_dat_concentrations():
    mdata = MAGICCData()
    test_file = "20THCENTURY_MIDYEAR_CONCENTRATIONS.DAT"
    mdata.read(join(TEST_DATA_DIR, test_file))
    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "26/11/2009 11:29:06"
    assert mdata.metadata["magicc-version"] == "6.3.09, 25 November 2009"
    assert "PRE2005__MIDYEAR__CONCENTRATIONS" in mdata.metadata["header"]
    assert (
        "COLUMN_DESCRIPTION________________________________________"
        in mdata.metadata["header"]
    )

    assert (mdata.df["variable"].str.startswith("Atmospheric Concentrations|")).all()
    assert (mdata.df["region"] == "World").all()
    assert (mdata.df["todo"] == "SET").all()

    row = (
        (mdata.df["variable"] == "Atmospheric Concentrations|CO2 Equivalent")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1766)
        & (mdata.df["unit"] == "ppm")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 277.8388)

    row = (
        (
            mdata.df["variable"]
            == "Atmospheric Concentrations|CO2 Equivalent|Kyoto Gases"
        )
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1767)
        & (mdata.df["unit"] == "ppm")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 278.68732)

    row = (
        (
            mdata.df["variable"]
            == "Atmospheric Concentrations|HFC134a Equivalent|F Gases"
        )
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2005)
        & (mdata.df["unit"] == "ppt")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 126.7694)

    row = (
        (
            mdata.df["variable"]
            == "Atmospheric Concentrations|CFC12 Equivalent|Montreal Protocol Halogen Gases"
        )
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2005)
        & (mdata.df["unit"] == "ppt")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 1003.5801)

    row = (
        (mdata.df["variable"] == "Atmospheric Concentrations|CH3Cl")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2005)
        & (mdata.df["unit"] == "ppt")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 538)


def test_load_rcp_historical_dat_forcings():
    mdata = MAGICCData()
    test_file = "20THCENTURY_MIDYEAR_RADFORCING.DAT"
    mdata.read(join(TEST_DATA_DIR, test_file))
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

    assert (mdata.df["variable"].str.startswith("Radiative Forcing")).all()
    assert (mdata.df["region"] == "World").all()
    assert (mdata.df["todo"] == "SET").all()
    assert (mdata.df["unit"] == "W / m^2").all()

    row = (
        (mdata.df["variable"] == "Radiative Forcing")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1766)
        & (mdata.df["unit"] == "W / m^2")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.12602655)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|Solar")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1767)
        & (mdata.df["unit"] == "W / m^2")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0070393750)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|Black Carbon on Snow")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2005)
        & (mdata.df["unit"] == "W / m^2")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.10018846)


def test_load_rcp_projections_dat_emissions():
    mdata = MAGICCData()
    test_file = "RCP3PD_EMISSIONS.DAT"
    mdata.read(join(TEST_DATA_DIR, test_file))
    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "26/11/2009 11:29:06"
    assert mdata.metadata["magicc-version"] == "6.3.09, 25 November 2009"
    assert "RCP3PD__EMISSIONS" in mdata.metadata["header"]
    assert (
        "COLUMN_DESCRIPTION________________________________________"
        in mdata.metadata["header"]
    )

    assert (mdata.df["variable"].str.startswith("Emissions|")).all()
    assert (mdata.df["region"] == "World").all()
    assert (mdata.df["todo"] == "SET").all()

    row = (
        (mdata.df["variable"] == "Emissions|CO2|MAGICC Fossil and Industrial")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2100)
        & (mdata.df["unit"] == "Gt C / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, -0.9308)

    row = (
        (mdata.df["variable"] == "Emissions|CH4")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1767)
        & (mdata.df["unit"] == "Mt CH4 / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 2.4364481)

    row = (
        (mdata.df["variable"] == "Emissions|CH3Cl")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2500)
        & (mdata.df["unit"] == "kt CH3Cl / yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 3511.0820)


def test_load_rcp_projections_dat_concentrations():
    mdata = MAGICCData()
    test_file = "RCP3PD_MIDYEAR_CONCENTRATIONS.DAT"
    mdata.read(join(TEST_DATA_DIR, test_file))
    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "26/11/2009 11:29:06"
    assert mdata.metadata["magicc-version"] == "6.3.09, 25 November 2009"
    assert "RCP3PD__MIDYEAR__CONCENTRATIONS" in mdata.metadata["header"]
    assert (
        "COLUMN_DESCRIPTION________________________________________"
        in mdata.metadata["header"]
    )

    assert (mdata.df["variable"].str.startswith("Atmospheric Concentrations|")).all()
    assert (mdata.df["region"] == "World").all()
    assert (mdata.df["todo"] == "SET").all()

    row = (
        (mdata.df["variable"] == "Atmospheric Concentrations|CO2 Equivalent")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1766)
        & (mdata.df["unit"] == "ppm")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 277.8388)

    row = (
        (
            mdata.df["variable"]
            == "Atmospheric Concentrations|CO2 Equivalent|Kyoto Gases"
        )
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2100)
        & (mdata.df["unit"] == "ppm")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 475.19275)

    row = (
        (
            mdata.df["variable"]
            == "Atmospheric Concentrations|HFC134a Equivalent|F Gases"
        )
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2500)
        & (mdata.df["unit"] == "ppt")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 900.02269)

    row = (
        (
            mdata.df["variable"]
            == "Atmospheric Concentrations|CFC12 Equivalent|Montreal Protocol Halogen Gases"
        )
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2500)
        & (mdata.df["unit"] == "ppt")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 10.883049)

    row = (
        (mdata.df["variable"] == "Atmospheric Concentrations|CH3Cl")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2500)
        & (mdata.df["unit"] == "ppt")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 538.02891)


def test_load_rcp_projections_dat_forcings():
    mdata = MAGICCData()
    test_file = "RCP3PD_MIDYEAR_RADFORCING.DAT"
    mdata.read(join(TEST_DATA_DIR, test_file))
    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "26/11/2009 11:29:06 (updated description)"
    assert mdata.metadata["magicc-version"] == "6.3.09, 25 November 2009"
    assert "RCP3PD__RADIATIVE FORCINGS" in mdata.metadata["header"]
    assert (
        "COLUMN_DESCRIPTION________________________________________"
        in mdata.metadata["header"]
    )

    assert (mdata.df["variable"].str.startswith("Radiative Forcing")).all()
    assert (mdata.df["region"] == "World").all()
    assert (mdata.df["todo"] == "SET").all()
    assert (mdata.df["unit"] == "W / m^2").all()

    row = (
        (mdata.df["variable"] == "Radiative Forcing")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1766)
        & (mdata.df["unit"] == "W / m^2")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.12602655)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|Volcanic")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1766)
        & (mdata.df["unit"] == "W / m^2")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.11622211)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|Anthropogenic")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1766)
        & (mdata.df["unit"] == "W / m^2")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.016318812)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|Greenhouse Gases")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1766)
        & (mdata.df["unit"] == "W / m^2")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.015363514)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|Greenhouse Gases|Kyoto Gases")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1766)
        & (mdata.df["unit"] == "W / m^2")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.015363514)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|CO2, CH4 and N2O")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1766)
        & (mdata.df["unit"] == "W / m^2")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.015363514)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|F Gases")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1766)
        & (mdata.df["unit"] == "W / m^2")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|Montreal Protocol Halogen Gases")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1766)
        & (mdata.df["unit"] == "W / m^2")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|Aerosols|Direct Effect")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1766)
        & (mdata.df["unit"] == "W / m^2")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.000017767194)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|Aerosols|MAGICC AFOLU")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1766)
        & (mdata.df["unit"] == "W / m^2")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.00025010344)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|Mineral Dust")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1766)
        & (mdata.df["unit"] == "W / m^2")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, -0.00019073512)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|Aerosols|Indirect Effect")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1766)
        & (mdata.df["unit"] == "W / m^2")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, -0.00080145063)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|Stratospheric Ozone")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1766)
        & (mdata.df["unit"] == "W / m^2")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|Tropospheric Ozone")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1766)
        & (mdata.df["unit"] == "W / m^2")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0014060381)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|CH4 Oxidation Stratospheric H2O")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1766)
        & (mdata.df["unit"] == "W / m^2")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.00060670657)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|Land-use Change")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1766)
        & (mdata.df["unit"] == "W / m^2")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, -0.00038147024)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|Solar")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2100)
        & (mdata.df["unit"] == "W / m^2")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.19056187)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|Black Carbon on Snow")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2500)
        & (mdata.df["unit"] == "W / m^2")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.038412234)


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
    mdata = MAGICCData()
    test_file = "MAGCFG_BULKPARAS.CFG"
    expected_error_msg = (
        r"^"
        + re.escape("MAGCCInput cannot read .CFG files like ")
        + r".*{}".format(test_file)
        + re.escape(", please use pymagicc.io.read_cfg_file")
        + r"$"
    )

    with pytest.raises(ValueError, match=expected_error_msg):
        mdata.read(join(MAGICC6_DIR, test_file))


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


def test_load_out():
    mdata = MAGICCData()
    mdata.read(join(TEST_OUT_DIR, "DAT_SURFACE_TEMP.OUT"))

    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "2018-09-23 18:33"
    assert (
        mdata.metadata["magicc-version"]
        == "6.8.01 BETA, 7th July 2012 - live.magicc.org"
    )
    assert "__MAGICC 6.X DATA OUTPUT FILE__" in mdata.metadata["header"]
    assert (mdata.df.todo == "N/A").all()
    assert (mdata.df.unit == "K").all()
    assert (mdata.df.variable == "Surface Temperature").all()

    row = (
        (mdata.df["variable"] == "Surface Temperature")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1767)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0079979091)

    row = (
        (mdata.df["variable"] == "Surface Temperature")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1965)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, -0.022702952)

    row = (
        (mdata.df["variable"] == "Surface Temperature")
        & (mdata.df["region"] == "World|Northern Hemisphere|Ocean")
        & (mdata.df["time"] == 1769)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.010526585)

    row = (
        (mdata.df["variable"] == "Surface Temperature")
        & (mdata.df["region"] == "World|Southern Hemisphere|Ocean")
        & (mdata.df["time"] == 1820)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, -0.25062424)

    row = (
        (mdata.df["variable"] == "Surface Temperature")
        & (mdata.df["region"] == "World|Northern Hemisphere|Land")
        & (mdata.df["time"] == 2093)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 1.8515042)

    row = (
        (mdata.df["variable"] == "Surface Temperature")
        & (mdata.df["region"] == "World|Southern Hemisphere|Land")
        & (mdata.df["time"] == 1765)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0)


def test_load_out_slash_and_caret_in_rf_units():
    mdata = MAGICCData()
    mdata.read(join(TEST_OUT_DIR, "DAT_SOXB_RF.OUT"))

    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "2018-09-23 18:33"
    assert (
        mdata.metadata["magicc-version"]
        == "6.8.01 BETA, 7th July 2012 - live.magicc.org"
    )
    assert "__MAGICC 6.X DATA OUTPUT FILE__" in mdata.metadata["header"]
    assert (mdata.df.todo == "N/A").all()
    assert (mdata.df.unit == "W / m^2").all()
    assert (mdata.df.variable == "Radiative Forcing|SOx|MAGICC AFOLU").all()

    row = (
        (mdata.df["variable"] == "Radiative Forcing|SOx|MAGICC AFOLU")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1767)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, -0.00025099784)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|SOx|MAGICC AFOLU")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1965)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, -0.032466593)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|SOx|MAGICC AFOLU")
        & (mdata.df["region"] == "World|Northern Hemisphere|Ocean")
        & (mdata.df["time"] == 1769)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, -0.0014779559)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|SOx|MAGICC AFOLU")
        & (mdata.df["region"] == "World|Southern Hemisphere|Ocean")
        & (mdata.df["time"] == 1820)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, -0.00039305876)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|SOx|MAGICC AFOLU")
        & (mdata.df["region"] == "World|Northern Hemisphere|Land")
        & (mdata.df["time"] == 2093)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, -0.024316933)

    row = (
        (mdata.df["variable"] == "Radiative Forcing|SOx|MAGICC AFOLU")
        & (mdata.df["region"] == "World|Southern Hemisphere|Land")
        & (mdata.df["time"] == 1765)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0)


def test_load_out_slash_and_caret_in_heat_content_units():
    mdata = MAGICCData()
    mdata.read(join(TEST_OUT_DIR, "DAT_HEATCONTENT_AGGREG_DEPTH1.OUT"))

    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "2018-09-23 18:33"
    assert (
        mdata.metadata["magicc-version"]
        == "6.8.01 BETA, 7th July 2012 - live.magicc.org"
    )
    assert "__MAGICC 6.X DATA OUTPUT FILE__" in mdata.metadata["header"]
    assert (mdata.df.todo == "N/A").all()
    assert (mdata.df.unit == "10^22J").all()
    assert (mdata.df.variable == "Aggregated Ocean Heat Content|Depth 1").all()

    row = (
        (mdata.df["variable"] == "Aggregated Ocean Heat Content|Depth 1")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1767)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.046263236)

    row = (
        (mdata.df["variable"] == "Aggregated Ocean Heat Content|Depth 1")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1965)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 3.4193050)

    row = (
        (mdata.df["variable"] == "Aggregated Ocean Heat Content|Depth 1")
        & (mdata.df["region"] == "World|Northern Hemisphere|Ocean")
        & (mdata.df["time"] == 1769)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.067484257)

    row = (
        (mdata.df["variable"] == "Aggregated Ocean Heat Content|Depth 1")
        & (mdata.df["region"] == "World|Southern Hemisphere|Ocean")
        & (mdata.df["time"] == 1820)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, -4.2688102)

    row = (
        (mdata.df["variable"] == "Aggregated Ocean Heat Content|Depth 1")
        & (mdata.df["region"] == "World|Northern Hemisphere|Land")
        & (mdata.df["time"] == 2093)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0)

    row = (
        (mdata.df["variable"] == "Aggregated Ocean Heat Content|Depth 1")
        & (mdata.df["region"] == "World|Southern Hemisphere|Land")
        & (mdata.df["time"] == 1765)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0)


def test_load_out_ocean_layers():
    mdata = MAGICCData()
    mdata.read(join(TEST_OUT_DIR, "TEMP_OCEANLAYERS.OUT"))

    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "2018-09-23 18:33"
    assert (
        mdata.metadata["magicc-version"]
        == "6.8.01 BETA, 7th July 2012 - live.magicc.org"
    )
    assert (
        "__MAGICC 6.X TEMP_OCEANLAYERS DATA OUTPUT FILE__" in mdata.metadata["header"]
    )
    assert (mdata.df.todo == "N/A").all()
    assert (mdata.df.unit == "K").all()

    row = (
        (mdata.df["variable"] == "Ocean Temperature|Layer 1")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1765)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0)

    row = (
        (mdata.df["variable"] == "Ocean Temperature|Layer 3")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 1973)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.10679213)

    row = (
        (mdata.df["variable"] == "Ocean Temperature|Layer 50")
        & (mdata.df["region"] == "World")
        & (mdata.df["time"] == 2100)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.13890633)


def test_load_out_ocean_layers_hemisphere():
    mdata = MAGICCData()
    mdata.read(join(TEST_OUT_DIR, "TEMP_OCEANLAYERS_NH.OUT"))

    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "2018-09-23 18:33"
    assert (
        mdata.metadata["magicc-version"]
        == "6.8.01 BETA, 7th July 2012 - live.magicc.org"
    )
    assert (
        "__MAGICC 6.X TEMP_OCEANLAYERS DATA OUTPUT FILE__" in mdata.metadata["header"]
    )
    assert (mdata.df.todo == "N/A").all()
    assert (mdata.df.unit == "K").all()

    row = (
        (mdata.df["variable"] == "Ocean Temperature|Layer 1")
        & (mdata.df["region"] == "World|Northern Hemisphere|Ocean")
        & (mdata.df["time"] == 1765)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.0)

    row = (
        (mdata.df["variable"] == "Ocean Temperature|Layer 3")
        & (mdata.df["region"] == "World|Northern Hemisphere|Ocean")
        & (mdata.df["time"] == 1973)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.10679213)

    row = (
        (mdata.df["variable"] == "Ocean Temperature|Layer 50")
        & (mdata.df["region"] == "World|Northern Hemisphere|Ocean")
        & (mdata.df["time"] == 2100)
    )
    assert sum(row) == 1
    np.testing.assert_allclose(mdata.df[row].value, 0.13890633)


def test_load_parameters_out_with_magicc_input():
    mdata = MAGICCData()
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
        mdata.read(join(TEST_OUT_DIR, test_file))


xfail_msg = (
    "Output files have heaps of spurious spaces, need to decide what to do "
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


@pytest.mark.xfail(
    reason="Direct access not available in v2.0.0, will update with OpenSCM DataFrame in v2.1.0"
)
def test_direct_access():
    mdata = MAGICCData("HISTRCP_CO2I_EMIS.IN")
    mdata.read(join(MAGICC6_DIR))

    tvariable = "Emissions|CO2|MAGICC Fossil and Industrial"
    tregion = "World|R5LAM"
    tyear = 1983
    result = mdata.filter(variable=tvariable, region=tregion, year=tyear)
    expected = mdata.df[
        (mdata.df.variable == tvariable)
        & (mdata.df.region == tregion)
        & (mdata.df.year == tyear)
    ]
    pd.testing.assert_frame_equal(result, expected)


def test_proxy():
    mdata = MAGICCData()
    mdata.read(join(MAGICC6_DIR, "HISTRCP_CO2I_EMIS.IN"))

    # Get an attribute from the pandas DataFrame
    plot = mdata.plot
    assert plot.__module__ == "pandas.plotting._core"


def test_incomplete_filepath():
    mdata = MAGICCData()
    with pytest.raises(FileNotFoundError):
        mdata.read(join("/incomplete/dir/name"))

    with pytest.raises(FileNotFoundError):
        mdata.read(join("RCP26.SCEN"))


def test_invalid_name():
    mdata = MAGICCData()
    with pytest.raises(FileNotFoundError):
        mdata.read(join("/tmp", "MYNONEXISTANT.IN"))


def test_header_metadata():
    m = _InputReader("test")
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

    m = _InputReader("test")
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
    mdata = MAGICCData()

    assert mdata.df is None
    assert mdata.metadata == {}
    assert mdata.filepath is None


def test_set_lines():
    reader = _InputReader("test")
    with pytest.raises(FileNotFoundError):
        reader._set_lines()

    test_file = join(TEST_DATA_DIR, "HISTSSP_CO2I_EMIS.IN")
    assert isfile(test_file)

    reader = _InputReader(test_file)
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
    mi_writer = MAGICCData()
    mi_writer.read(join(starting_fpath, starting_fname))

    mi_writer.write(join(temp_dir, starting_fname), magicc_version=6)

    mi_written = MAGICCData()
    mi_written.read(join(temp_dir, starting_fname))

    mi_initial = MAGICCData()
    mi_initial.read(join(starting_fpath, starting_fname))

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

    pd.testing.assert_frame_equal(
        mi_written.df.sort_values(by=mi_written.df.columns.tolist()).reset_index(
            drop=True
        ),
        mi_initial.df.sort_values(by=mi_initial.df.columns.tolist()).reset_index(
            drop=True
        ),
    )


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
        mdata = MAGICCData()
        mdata.read(join(MAGICC6_DIR, file_to_read))


@pytest.mark.parametrize("file_to_read", [f for f in TEST_OUT_FILES])
def test_can_read_all_valid_files_in_magicc6_out_dir(file_to_read):
    if file_to_read.endswith(("PARAMETERS.OUT")):
        read_cfg_file(join(TEST_OUT_DIR, file_to_read))
    else:
        for p in INVALID_OUT_FILES:
            if re.match(p, file_to_read):
                return
        mdata = MAGICCData()
        mdata.read(join(TEST_OUT_DIR, file_to_read))


@pytest.mark.parametrize("file_to_read", [f for f in TEST_OUT_FILES])
def test_cant_read_all_invalid_files_in_magicc6_out_dir(file_to_read):
    valid_filepath = True
    for p in INVALID_OUT_FILES:
        if re.match(p, file_to_read):
            valid_filepath = False

    if valid_filepath:
        return

    mdata = MAGICCData()
    if ("SUBANN" in file_to_read) or ("VOLCANIC_RF.BINOUT" in file_to_read):
        error_msg = (
            r"^.*"
            + re.escape(": Only annual binary files can currently be processed")
            + r".*$"
        )
        with pytest.raises(InvalidTemporalResError, match=error_msg):
            mdata.read(join(TEST_OUT_DIR, file_to_read))
    else:
        error_msg = (
            r"^.*"
            + re.escape(
                "is in an odd format for which we will never provide a reader/writer"
            )
            + r".*$"
        )
        with pytest.raises(NoReaderWriterError, match=error_msg):
            mdata.read(join(TEST_OUT_DIR, file_to_read))


@pytest.mark.parametrize(
    "file_to_read",
    [f for f in listdir(TEST_OUT_DIR) if f.endswith("BINOUT") and f.startswith("DAT_")],
)
def test_bin_and_ascii_equal(file_to_read):
    try:
        mdata_bin = MAGICCData()
        mdata_bin.read(join(TEST_OUT_DIR, file_to_read))
    except InvalidTemporalResError:
        # Some BINOUT files are on a subannual time scale and cannot be read (yet)
        return

    assert (mdata_bin.df.unit == "unknown").all()
    assert (mdata_bin.df.todo == "SET").all()

    mdata_ascii = MAGICCData()
    mdata_ascii.read(join(TEST_OUT_DIR, file_to_read.replace("BINOUT", "OUT")))

    # There are some minor differences between in the dataframes due to availability of metadata in BINOUT files
    drop_axes = ["unit", "todo"]
    mdata_ascii.df = mdata_ascii.df.drop(drop_axes, axis="columns")
    mdata_bin.df = mdata_bin.df.drop(drop_axes, axis="columns")
    pd.testing.assert_frame_equal(mdata_ascii.df, mdata_bin.df)


def test_magicc_data_append_unset():
    tfilepath = "mocked/out/here.txt"
    tmetadata = {"mock": 12, "mock 2": "written here"}
    tdf = pd.DataFrame({"test": np.array([1, 2, 3])})

    mdata = MAGICCData()
    mdata._read_and_return_metadata_df = MagicMock(return_value=(tmetadata, tdf))

    assert mdata.df is None
    mdata.append(tfilepath)

    mdata._read_and_return_metadata_df.assert_called_with(tfilepath)

    assert mdata.metadata == tmetadata
    pd.testing.assert_frame_equal(mdata.df, tdf)


def test_magicc_data_append():
    tfilepath = "mocked/out/here.txt"

    tmetadata_append = {"mock 12": 7, "mock 24": "written here too"}
    tdf_append = pd.DataFrame({"test": np.array([-1, 12, 1.33])})

    tmetadata_init = {"mock": 12, "mock 2": "written here"}
    tdf_init = pd.DataFrame({"test": np.array([1, 2, 3])})

    mdata = MAGICCData()
    mdata._read_and_return_metadata_df = MagicMock(
        return_value=(tmetadata_append, tdf_append)
    )
    mdata.df = tdf_init
    mdata.metadata = tmetadata_init

    mdata.append(tfilepath)

    mdata._read_and_return_metadata_df.assert_called_with(tfilepath)

    expected_metadata = deepcopy(tmetadata_init)
    expected_metadata.update(tmetadata_append)
    assert mdata.metadata == expected_metadata
    pd.testing.assert_frame_equal(mdata.df, pd.concat([tdf_init, tdf_append]))


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
    mdata = MAGICCData()
    mdata.read(join(TEST_DATA_DIR, "RCP3PD_EMISSIONS.DAT"))
    base = mdata.df.copy()
    base["todo"] = "SET"

    mdata.read(join(MAGICC6_DIR, "RCP60.SCEN"))
    scen = mdata.df.copy()

    res = join_timeseries(base=base, overwrite=scen, join_linear=[2005, 2012])

    row = (
        (res["variable"] == "Emissions|CO2|MAGICC Fossil and Industrial")
        & (res["region"] == "World")
        & (res["time"] == 2000)
        & (res["unit"] == "Gt C / yr")
        & (res["todo"] == "SET")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(res[row].value, 6.735)

    row = (
        (res["variable"] == "Emissions|CO2|MAGICC Fossil and Industrial")
        & (res["region"] == "World")
        & (res["time"] == 2008)
        & (res["unit"] == "Gt C / yr")
        & (res["todo"] == "SET")
    )
    assert sum(row) == 1
    val_2012 = 8.5115 + (8.9504 - 8.5115) * 2 / 10
    expected = 7.971 + (val_2012 - 7.971) / 7 * 3
    np.testing.assert_allclose(res[row].value, expected)

    row = (
        (res["variable"] == "Emissions|CO2|MAGICC Fossil and Industrial")
        & (res["region"] == "World")
        & (res["time"] == 2015)
        & (res["unit"] == "Gt C / yr")
        & (res["todo"] == "SET")
    )
    assert sum(row) == 1
    expected = 8.5115 + (8.9504 - 8.5115) / 2
    np.testing.assert_allclose(res[row].value, expected)

    row = (
        (res["variable"] == "Emissions|CFC11")
        & (res["region"] == "World")
        & (res["time"] == 1995)
        & (res["unit"] == "kt CFC11 / yr")
        & (res["todo"] == "SET")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(res[row].value, 119.235)

    row = (
        (res["variable"] == "Emissions|CFC11")
        & (res["region"] == "World")
        & (res["time"] == 2015)
        & (res["unit"] == "kt CFC11 / yr")
        & (res["todo"] == "SET")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(res[row].value, 36.338)


@patch("pymagicc.io.MAGICCData")
@patch("pymagicc.io._join_timeseries_mdata")
def test_join_timeseries_unit(mock_join_timeseries_mdata, mock_magicc_data):
    tbase = 13
    toverwrite = 14
    tdf = "mocked as well"
    toutput = "mocked output"

    mock_magicc_data.return_value.df.return_value = tdf
    mock_join_timeseries_mdata.return_value = toutput

    res = join_timeseries(base=tbase, overwrite=toverwrite)

    assert res == toutput

    mock_join_timeseries_mdata.assert_called_with(tbase, toverwrite, None)


@pytest.fixture(scope="function")
def join_base_df():
    bdf = pd.DataFrame(
        [
            [2000, "Emissions|CO2", "GtC/yr", "World", 1.0],
            [2010, "Emissions|CO2", "GtC/yr", "World", 2.0],
            [2020, "Emissions|CO2", "GtC/yr", "World", 3.0],
            [2000, "Emissions|CH4", "MtCH4/yr", "World", 1.1],
            [2010, "Emissions|CH4", "MtCH4/yr", "World", 1.2],
            [2020, "Emissions|CH4", "MtCH4/yr", "World", 1.3],
        ],
        columns=["time", "variable", "unit", "region", "value"],
    )

    yield bdf


@pytest.fixture(scope="function")
def join_overwrite_df():
    odf = pd.DataFrame(
        [
            [2015, "Emissions|CO2", "GtC/yr", "World", 1.0],
            [2050, "Emissions|CO2", "GtC/yr", "World", 2.0],
            [2100, "Emissions|CO2", "GtC/yr", "World", 3.0],
        ],
        columns=["time", "variable", "unit", "region", "value"],
    )

    yield odf


def test_join_timeseries_mdata_no_harmonisation(join_base_df, join_overwrite_df):
    msg = (
        "nan values in joint arrays, this is likely because your input "
        "timeseries do not all cover the same span"
    )
    with warnings.catch_warnings(record=True) as warn_result:
        res = _join_timeseries_mdata(
            base=join_base_df, overwrite=join_overwrite_df, join_linear=None
        )

    assert len(warn_result) == 1
    assert str(warn_result[0].message) == msg

    row = (
        (res["variable"] == "Emissions|CO2")
        & (res["region"] == "World")
        & (res["time"] == 2005)
        & (res["unit"] == "GtC/yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(res[row].value, 1.5)

    row = (
        (res["variable"] == "Emissions|CO2")
        & (res["region"] == "World")
        & (res["time"] == 2015)
        & (res["unit"] == "GtC/yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(res[row].value, 1.0)

    row = (
        (res["variable"] == "Emissions|CO2")
        & (res["region"] == "World")
        & (res["time"] == 2020)
        & (res["unit"] == "GtC/yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(res[row].value, 1 + (2 - 1) / 35 * 5)

    row = (
        (res["variable"] == "Emissions|CH4")
        & (res["region"] == "World")
        & (res["time"] == 2020)
        & (res["unit"] == "MtCH4/yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(res[row].value, 1.3)

    row = (
        (res["variable"] == "Emissions|CH4")
        & (res["region"] == "World")
        & (res["time"] == 2100)
        & (res["unit"] == "MtCH4/yr")
    )
    assert sum(row) == 1
    assert np.isnan(res[row].value).all()


def test_join_timeseries_mdata_harmonisation(join_base_df, join_overwrite_df):
    res = _join_timeseries_mdata(
        base=join_base_df, overwrite=join_overwrite_df, join_linear=[2010, 2020]
    )

    row = (
        (res["variable"] == "Emissions|CO2")
        & (res["region"] == "World")
        & (res["time"] == 2012)
        & (res["unit"] == "GtC/yr")
    )
    assert sum(row) == 1
    overwrite_co2_val_2020 = 1 + (2 - 1) / 35 * 5
    expected = 2 + (overwrite_co2_val_2020 - 2) / 10 * 2
    np.testing.assert_allclose(res[row].value, expected)

    row = (
        (res["variable"] == "Emissions|CO2")
        & (res["region"] == "World")
        & (res["time"] == 2050)
        & (res["unit"] == "GtC/yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(res[row].value, 2.0)

    row = (
        (res["variable"] == "Emissions|CH4")
        & (res["region"] == "World")
        & (res["time"] == 2020)
        & (res["unit"] == "MtCH4/yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(res[row].value, 1.3)


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

    join_base_df = join_base_df[join_base_df["variable"] == "Emissions|CH4"]
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

    mock_magicc_data.return_value.read = MagicMock()
    mock_magicc_data.return_value.df = tmdata

    mock_join_timeseries_mdata.return_value = treturn

    res = join_timeseries(
        base=tbase, overwrite=toverwrite
    )

    assert res == treturn

    assert mock_magicc_data.return_value.read.call_count == 2
    mock_join_timeseries_mdata.assert_called_with(tmdata, tmdata, None)

# TODO: improve join timeseries so it can also handle datetimes in the time axis
