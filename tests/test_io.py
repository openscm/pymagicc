from os import remove, listdir
from os.path import dirname, join, isfile, basename
from tempfile import mkstemp, mkdtemp
from shutil import rmtree

import numpy as np
import pandas as pd
import re
import pkg_resources
import pytest
from unittest.mock import patch
import f90nml

from pymagicc.api import MAGICC6
from pymagicc.io import (
    MAGICCData,
    _InputReader,
    _ConcInReader,
    _ScenWriter,
    read_cfg_file,
    get_special_scen_code,
    NoReaderWriterError,
    InvalidTemporalResError
)

MAGICC6_DIR = pkg_resources.resource_filename("pymagicc", "MAGICC6/run")
TEST_DATA_DIR = join(dirname(__file__), "test_data")
TEST_OUT_DIR = join(TEST_DATA_DIR, "out_dir")

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
    r"TEMP_OCEANLAYERS\.BINOUT",
    r"TIMESERIESMIX.*OUT",
    r"SUMMARY_INDICATORS.OUT",
]


def test_cant_find_reader_writer():
    mdata = MAGICCData()
    test_filename = "HISTRCP_CO2I_EMIS.txt"

    expected_message = (
        r"^"
        + re.escape("Couldn't find appropriate reader for {}.".format(test_filename))
        + r"\n"
        + re.escape(
            "The file must be one "
            "of the following types and the filename must match its "
            "corresponding regular expression:"
        )
        + r"(\n.*)*"  # dicts aren't ordered in Python3.5
        + re.escape("SCEN: ^.*\\.SCEN$")
        + r"(\n.*)*$"
    )

    with pytest.raises(ValueError, match=expected_message):
        mdata.read(TEST_DATA_DIR, test_filename)

    expected_message = expected_message.replace("reader", "writer")
    with pytest.raises(ValueError, match=expected_message):
        mdata.write(test_filename)


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
    assert mdata.df.index.names == ["YEAR"]
    assert mdata.df.columns.names == ["VARIABLE", "TODO", "UNITS", "REGION"]
    for key in ["units", "firstdatarow", "dattype"]:
        with pytest.raises(KeyError):
            mdata.metadata[key]
    assert isinstance(mdata.metadata["header"], str)


def test_load_magicc6_emis():
    mdata = MAGICCData()
    assert mdata.is_loaded == False
    mdata.read(MAGICC6_DIR, "HISTRCP_CO2I_EMIS.IN")
    generic_mdata_tests(mdata)

    np.testing.assert_allclose(
        mdata.df["CO2I_EMIS", "SET", "GtC", "R5ASIA"][2000], 1.7682027e000
    )


def test_load_magicc6_emis_hyphen_in_units():
    mdata = MAGICCData()
    assert mdata.is_loaded == False
    mdata.read(MAGICC6_DIR, "HISTRCP_N2OI_EMIS.IN")
    generic_mdata_tests(mdata)

    np.testing.assert_allclose(
        mdata.df["N2OI_EMIS", "SET", "MtN2O-N", "R5ASIA"][2000], 0.288028519
    )


def test_load_magicc5_emis():
    mdata = MAGICCData()
    assert mdata.is_loaded == False
    mdata.read(MAGICC6_DIR, "MARLAND_CO2I_EMIS.IN")
    generic_mdata_tests(mdata)

    np.testing.assert_allclose(
        mdata.df["CO2I_EMIS", "SET", "GtC", "NH"][2000], 6.20403698
    )
    np.testing.assert_allclose(
        mdata.df["CO2I_EMIS", "SET", "GtC", "SH"][2002], 0.495812385
    )
    np.testing.assert_allclose(mdata.df["CO2I_EMIS", "SET", "GtC", "SH"][1751], 0.0)


def test_load_magicc5_emis_not_renamed_error():
    mdata = MAGICCData()

    test_filepath = TEST_DATA_DIR
    test_filename = "MARLAND_CO2_EMIS_FOSSIL&IND.IN"

    expected_error_msg = re.escape(
        "Cannot determine variable from filename: {}".format(
            join(test_filepath, test_filename)
        )
    )
    with pytest.raises(ValueError, match=expected_error_msg):
        mdata.read(test_filepath, test_filename)


def test_load_magicc6_conc():
    mdata = MAGICCData()
    mdata.read(MAGICC6_DIR, "HISTRCP_CO2_CONC.IN")

    assert (mdata.df.columns.get_level_values("UNITS") == "ppm").all()
    generic_mdata_tests(mdata)
    np.testing.assert_allclose(
        mdata.df["CO2_CONC", "SET", "ppm", "GLOBAL"][1048], 2.80435733e002
    )


def test_load_magicc6_conc_old_style_name_umlaut_metadata():
    mdata = MAGICCData()
    mdata.read(MAGICC6_DIR, "HISTRCP_HFC245fa_CONC.IN")

    assert (mdata.df.columns.get_level_values("UNITS") == "ppt").all()
    assert mdata.metadata["data"] == "Global average mixing ratio"
    generic_mdata_tests(mdata)
    np.testing.assert_allclose(mdata.df["HFC245FA_CONC", "SET", "ppt", "GLOBAL"], 0.0)


def test_load_magicc6_conc_old_style_name_with_hyphen():
    mdata = MAGICCData()
    mdata.read(MAGICC6_DIR, "HISTRCP_HFC43-10_CONC.IN")

    assert (mdata.df.columns.get_level_values("UNITS") == "ppt").all()
    generic_mdata_tests(mdata)

    np.testing.assert_allclose(mdata.df["HFC4310_CONC", "SET", "ppt", "GLOBAL"], 0.0)


def test_load_magicc7_emis_umlaut_metadata():
    mdata = MAGICCData()
    mdata.read(TEST_DATA_DIR, "HISTSSP_CO2I_EMIS.IN")

    generic_mdata_tests(mdata)

    assert (
        mdata.metadata["contact"]
        == "Zebedee Nicholls, Australian-German Climate and Energy College, University of Melbourne, zebedee.nicholls@climate-energy-college.org"
    )
    assert mdata.metadata["description"] == "Test line by näme with ümlauts ëh ça"
    assert (mdata.df.columns.get_level_values("UNITS") == "GtC").all()
    # change read in to CO2I_EMIS
    np.testing.assert_allclose(
        mdata.df["CO2I_EMIS", "SET", "GtC", "R6REF"][2013], 0.6638
    )
    np.testing.assert_allclose(
        mdata.df["CO2I_EMIS", "SET", "GtC", "R6ASIA"][2000], 1.6911
    )


def test_load_ot():
    mdata = MAGICCData()
    mdata.read(MAGICC6_DIR, "MIXED_NOXI_OT.IN")

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

    assert (mdata.df.columns.get_level_values("UNITS") == "DIMENSIONLESS").all()
    assert (mdata.df.columns.get_level_values("TODO") == "SET").all()
    assert (mdata.df.columns.get_level_values("VARIABLE") == "NOXI_OT").all()

    np.testing.assert_allclose(
        mdata.df["NOXI_OT", "SET", "DIMENSIONLESS", "NHOCEAN"][1765], 0.00668115649
    )
    np.testing.assert_allclose(
        mdata.df["NOXI_OT", "SET", "DIMENSIONLESS", "NHLAND"][1865], 0.526135104
    )
    np.testing.assert_allclose(
        mdata.df["NOXI_OT", "SET", "DIMENSIONLESS", "SHOCEAN"][1965], 0.612718845
    )
    np.testing.assert_allclose(
        mdata.df["NOXI_OT", "SET", "DIMENSIONLESS", "SHLAND"][2000], 3.70377980
    )


def test_load_rf():
    mdata = MAGICCData()
    mdata.read(MAGICC6_DIR, "GISS_BCB_RF.IN")

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

    assert (mdata.df.columns.get_level_values("UNITS") == "W/m2").all()
    assert (mdata.df.columns.get_level_values("TODO") == "SET").all()
    assert (mdata.df.columns.get_level_values("VARIABLE") == "BCB_RF").all()

    np.testing.assert_allclose(mdata.df["BCB_RF", "SET", "W/m2", "NHOCEAN"][1765], 0.0)
    np.testing.assert_allclose(
        mdata.df["BCB_RF", "SET", "W/m2", "NHLAND"][1865], 0.268436597
    )
    np.testing.assert_allclose(
        mdata.df["BCB_RF", "SET", "W/m2", "SHOCEAN"][1965], 0.443357552
    )
    np.testing.assert_allclose(
        mdata.df["BCB_RF", "SET", "W/m2", "SHLAND"][2000], 1.53987244
    )


def test_load_solar_rf():
    mdata = MAGICCData()
    mdata.read(MAGICC6_DIR, "HISTRCP6SCP6to45_SOLAR_RF.IN")

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

    assert (mdata.df.columns.get_level_values("UNITS") == "W/m2").all()
    assert (mdata.df.columns.get_level_values("TODO") == "SET").all()
    assert (mdata.df.columns.get_level_values("VARIABLE") == "SOLAR_RF").all()
    assert (mdata.df.columns.get_level_values("REGION") == "GLOBAL").all()

    np.testing.assert_allclose(
        mdata.df["SOLAR_RF", "SET", "W/m2", "GLOBAL"][1610], 0.0149792391
    )
    np.testing.assert_allclose(
        mdata.df["SOLAR_RF", "SET", "W/m2", "GLOBAL"][1865], -0.00160201087
    )
    np.testing.assert_allclose(
        mdata.df["SOLAR_RF", "SET", "W/m2", "GLOBAL"][1965], 0.0652917391
    )
    np.testing.assert_allclose(
        mdata.df["SOLAR_RF", "SET", "W/m2", "GLOBAL"][2183], 0.0446329891
    )
    np.testing.assert_allclose(
        mdata.df["SOLAR_RF", "SET", "W/m2", "GLOBAL"][2600], 0.121325148
    )


def test_load_volcanic_rf():
    mdata = MAGICCData()
    mdata.read(MAGICC6_DIR, "HIST_VOLCANIC_RF.MON")

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

    assert (mdata.df.columns.get_level_values("UNITS") == "W/m2").all()
    assert (mdata.df.columns.get_level_values("TODO") == "SET").all()
    assert (mdata.df.columns.get_level_values("VARIABLE") == "VOLCANIC_RF").all()

    np.testing.assert_allclose(
        mdata.df["VOLCANIC_RF", "SET", "W/m2", "NHLAND"][1000.042], 0.0
    )
    np.testing.assert_allclose(
        mdata.df["VOLCANIC_RF", "SET", "W/m2", "NHLAND"][1002.542], -0.0187500000
    )
    np.testing.assert_allclose(
        mdata.df["VOLCANIC_RF", "SET", "W/m2", "NHOCEAN"][1013.208], 0.0
    )
    np.testing.assert_allclose(
        mdata.df["VOLCANIC_RF", "SET", "W/m2", "SHOCEAN"][1994.125], -0.6345
    )
    np.testing.assert_allclose(
        mdata.df["VOLCANIC_RF", "SET", "W/m2", "SHLAND"][2006.958], 0.0
    )


def test_load_scen():
    mdata = MAGICCData()
    mdata.read(MAGICC6_DIR, "RCP26.SCEN")

    generic_mdata_tests(mdata)

    assert (
        mdata.metadata["date"]
        == "26/11/2009 11:29:06; MAGICC-VERSION: 6.3.09, 25 November 2009"
    )
    assert "Final RCP3PD with constant emissions" in mdata.metadata["header"]

    np.testing.assert_allclose(
        mdata.df["CO2I_EMIS", "SET", "GtC", "WORLD"][2000], 6.7350
    )
    np.testing.assert_allclose(
        mdata.df["N2O_EMIS", "SET", "MtN2O-N", "WORLD"][2002], 7.5487
    )
    np.testing.assert_allclose(
        mdata.df["HFC4310_EMIS", "SET", "kt", "WORLD"][2001], 0.6470
    )
    np.testing.assert_allclose(
        mdata.df["SOX_EMIS", "SET", "MtS", "R5OECD"][2005], 11.9769
    )
    np.testing.assert_allclose(
        mdata.df["NMVOC_EMIS", "SET", "Mt", "R5OECD"][2050], 18.2123
    )
    np.testing.assert_allclose(mdata.df["HFC23_EMIS", "SET", "kt", "R5REF"][2100], 0.0)
    np.testing.assert_allclose(
        mdata.df["HFC125_EMIS", "SET", "kt", "R5REF"][2125], 5.2133
    )
    np.testing.assert_allclose(
        mdata.df["HFC143A_EMIS", "SET", "kt", "R5ASIA"][2040], 33.3635
    )
    np.testing.assert_allclose(
        mdata.df["SF6_EMIS", "SET", "kt", "R5ASIA"][2040], 0.8246
    )
    np.testing.assert_allclose(
        mdata.df["CO2B_EMIS", "SET", "GtC", "R5MAF"][2050], -0.0125
    )
    np.testing.assert_allclose(
        mdata.df["CH4_EMIS", "SET", "MtCH4", "R5MAF"][2070], 37.6218
    )
    np.testing.assert_allclose(
        mdata.df["NOX_EMIS", "SET", "MtN", "R5LAM"][2080], 1.8693
    )
    np.testing.assert_allclose(mdata.df["BC_EMIS", "SET", "Mt", "R5LAM"][2090], 0.4254)
    np.testing.assert_allclose(mdata.df["NH3_EMIS", "SET", "MtN", "BUNKERS"][2000], 0.0)
    np.testing.assert_allclose(mdata.df["SF6_EMIS", "SET", "kt", "BUNKERS"][2002], 0.0)


def test_load_scen_sres():
    mdata = MAGICCData()
    mdata.read(MAGICC6_DIR, "SRESA1B.SCEN")

    generic_mdata_tests(mdata)

    assert "Antero Hot Springs" in mdata.metadata["header"]

    np.testing.assert_allclose(
        mdata.df["CO2I_EMIS", "SET", "GtC", "WORLD"][2000], 6.8963
    )
    np.testing.assert_allclose(
        mdata.df["N2O_EMIS", "SET", "MtN2O-N", "WORLD"][1990], 6.6751
    )
    np.testing.assert_allclose(
        mdata.df["HFC4310_EMIS", "SET", "kt", "WORLD"][2000], 0.0000
    )
    np.testing.assert_allclose(
        mdata.df["SOX_EMIS", "SET", "MtS", "OECD90"][2010], 9.8762
    )
    np.testing.assert_allclose(
        mdata.df["NMVOC_EMIS", "SET", "Mt", "OECD90"][2050], 28.1940
    )
    np.testing.assert_allclose(mdata.df["HFC23_EMIS", "SET", "kt", "REF"][2100], 0.0624)
    np.testing.assert_allclose(
        mdata.df["HFC125_EMIS", "SET", "kt", "REF"][2100], 5.4067
    )
    np.testing.assert_allclose(
        mdata.df["HFC143A_EMIS", "SET", "kt", "ASIA"][2040], 15.4296
    )
    np.testing.assert_allclose(mdata.df["SF6_EMIS", "SET", "kt", "ASIA"][2040], 6.4001)
    np.testing.assert_allclose(mdata.df["CO2B_EMIS", "SET", "GtC", "ALM"][2050], 0.2613)
    np.testing.assert_allclose(
        mdata.df["CH4_EMIS", "SET", "MtCH4", "ALM"][2070], 130.1256
    )


def test_load_scen7():
    mdata = MAGICCData()
    mdata.read(TEST_DATA_DIR, "TESTSCEN7.SCEN7")

    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "13-Oct-2017 16:45:35"
    assert mdata.metadata["description"] == "TEST SCEN7 file"
    assert "NOTES" in mdata.metadata["header"]
    assert "~~~~~" in mdata.metadata["header"]
    assert "Some notes" in mdata.metadata["header"]

    np.testing.assert_allclose(
        mdata.df["CO2I_EMIS", "SET", "GtC", "WORLD"][2000], 6.7350
    )
    np.testing.assert_allclose(
        mdata.df["N2OI_EMIS", "SET", "MtN2O-N", "WORLD"][2002], 7.5487
    )
    np.testing.assert_allclose(
        mdata.df["HFC23_EMIS", "SET", "kt", "WORLD"][2001], 10.4328
    )
    np.testing.assert_allclose(
        mdata.df["SOX_EMIS", "SET", "MtS", "R6OECD90"][2005], 11.9769
    )
    np.testing.assert_allclose(
        mdata.df["NMVOC_EMIS", "SET", "Mt", "R6OECD90"][2050], 18.2123
    )
    np.testing.assert_allclose(mdata.df["HFC23_EMIS", "SET", "kt", "R6REF"][2100], 0.0)
    np.testing.assert_allclose(
        mdata.df["CH2Cl2_EMIS", "SET", "kt", "R6REF"][2125], 5.2133
    )
    np.testing.assert_allclose(
        mdata.df["HFC143A_EMIS", "SET", "kt", "R6ASIA"][2040], 33.3635
    )
    np.testing.assert_allclose(
        mdata.df["SO2F2_EMIS", "SET", "kt", "R6ASIA"][2040], 0.8246
    )
    np.testing.assert_allclose(
        mdata.df["CO2B_EMIS", "SET", "GtC", "R6MAF"][2050], -0.0125
    )
    np.testing.assert_allclose(
        mdata.df["CH4_EMIS", "SET", "MtCH4", "R6MAF"][2070], 37.6218
    )
    np.testing.assert_allclose(
        mdata.df["NOX_EMIS", "SET", "MtN", "R6LAM"][2080], 1.8693
    )
    np.testing.assert_allclose(mdata.df["BCB_EMIS", "SET", "Mt", "R6LAM"][2090], 0.4254)
    np.testing.assert_allclose(mdata.df["NH3_EMIS", "SET", "MtN", "BUNKERS"][2000], 0.0)
    np.testing.assert_allclose(
        mdata.df["SO2F2_EMIS", "SET", "kt", "BUNKERS"][2002], 0.0
    )


def test_load_prn():
    mdata = MAGICCData()
    mdata.read(MAGICC6_DIR, "RCPODS_WMO2006_Emissions_A1.prn")

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
    assert (mdata.df.columns.get_level_values("REGION") == "WORLD").all()
    assert (mdata.df.columns.get_level_values("TODO") == "SET").all()
    assert (mdata.df.columns.get_level_values("UNITS") == "t").all()

    np.testing.assert_allclose(mdata.df["CFC11_EMIS", "SET", "t", "WORLD"][1850], 0.0)
    np.testing.assert_allclose(mdata.df["CFC115_EMIS", "SET", "t", "WORLD"][1965], 444)
    np.testing.assert_allclose(
        mdata.df["HALON1211_EMIS", "SET", "t", "WORLD"][1996], 10743
    )
    np.testing.assert_allclose(
        mdata.df["HALON1301_EMIS", "SET", "t", "WORLD"][2017], 1062
    )
    np.testing.assert_allclose(
        mdata.df["CH3CL_EMIS", "SET", "t", "WORLD"][2500], 3511082
    )


def test_load_prn_no_units():
    mdata = MAGICCData()
    mdata.read(MAGICC6_DIR, "WMO2006_ODS_A1Baseline.prn")

    generic_mdata_tests(mdata)

    # top line should be ignored
    assert "6      1950      2100" not in mdata.metadata["header"]
    assert (
        "6/19/2006A1: Baseline emission file generated by John Daniel and Guus Velders"
        in mdata.metadata["header"]
    )

    assert (mdata.df.columns.get_level_values("REGION") == "WORLD").all()
    assert (mdata.df.columns.get_level_values("TODO") == "SET").all()
    assert (mdata.df.columns.get_level_values("UNITS") == "t").all()

    np.testing.assert_allclose(
        mdata.df["CFC12_EMIS", "SET", "t", "WORLD"][1950], 139965
    )
    np.testing.assert_allclose(
        mdata.df["CH3CL_EMIS", "SET", "t", "WORLD"][2100], 3511082
    )


def test_load_prn_mixing_ratios_years_label():
    mdata = MAGICCData()
    mdata.read(MAGICC6_DIR, "RCPODS_WMO2006_MixingRatios_A1.prn")

    generic_mdata_tests(mdata)

    # top line should be ignored
    assert "17      1850      2100" not in mdata.metadata["header"]
    assert mdata.metadata["data"] == "Global average mixing ratios"
    assert (
        mdata.metadata["description"]
        == "1951-2100 Baseline mixing ratio file generated by John Daniel and Guus Velders for WMO2006, Chapter 8. (2/3/06); CH3CL updated to reflect MAGICC6 timeseries after 1955 and lower 2000 concentrations closer to 535ppt in line with"
    )
    assert (mdata.df.columns.get_level_values("REGION") == "GLOBAL").all()
    assert (mdata.df.columns.get_level_values("TODO") == "SET").all()
    assert (mdata.df.columns.get_level_values("UNITS") == "ppt").all()

    np.testing.assert_allclose(
        mdata.df["CFC12_CONC", "SET", "ppt", "GLOBAL"][1850], 0.0
    )
    np.testing.assert_allclose(
        mdata.df["CFC114_CONC", "SET", "ppt", "GLOBAL"][1965], 5.058
    )
    np.testing.assert_allclose(
        mdata.df["HCFC141B_CONC", "SET", "ppt", "GLOBAL"][2059], 13.81
    )
    np.testing.assert_allclose(
        mdata.df["HALON2402_CONC", "SET", "ppt", "GLOBAL"][2091], 0.007
    )
    np.testing.assert_allclose(
        mdata.df["CH3CL_CONC", "SET", "ppt", "GLOBAL"][2100], 538
    )


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
        mdata.read(MAGICC6_DIR, test_file)


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
    assert cfg["THISFILE_SPECIFICATIONS"]["THISFILE_UNITS"] == "W/m2"


def test_load_out():
    mdata = MAGICCData()
    mdata.read(TEST_OUT_DIR, "DAT_SURFACE_TEMP.OUT")

    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "2018-09-23 18:33"
    assert (
        mdata.metadata["magicc-version"]
        == "6.8.01 BETA, 7th July 2012 - live.magicc.org"
    )
    assert "__MAGICC 6.X DATA OUTPUT FILE__" in mdata.metadata["header"]
    assert (mdata.df.columns.get_level_values("TODO") == "N/A").all()
    assert (mdata.df.columns.get_level_values("UNITS") == "K").all()

    np.testing.assert_allclose(
        mdata.df["SURFACE_TEMP", "N/A", "K", "GLOBAL"][1767], 0.0079979091
    )
    np.testing.assert_allclose(
        mdata.df["SURFACE_TEMP", "N/A", "K", "GLOBAL"][1965], -0.022702952
    )
    np.testing.assert_allclose(
        mdata.df["SURFACE_TEMP", "N/A", "K", "NHOCEAN"][1769], 0.010526585
    )
    np.testing.assert_allclose(
        mdata.df["SURFACE_TEMP", "N/A", "K", "SHOCEAN"][1820], -0.25062424
    )
    np.testing.assert_allclose(
        mdata.df["SURFACE_TEMP", "N/A", "K", "NHLAND"][2093], 1.8515042
    )
    np.testing.assert_allclose(
        mdata.df["SURFACE_TEMP", "N/A", "K", "SHLAND"][1765], 0.0
    )


def test_load_out_slash_and_caret_in_rf_units():
    mdata = MAGICCData()
    mdata.read(TEST_OUT_DIR, "DAT_SOXB_RF.OUT")

    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "2018-09-23 18:33"
    assert (
        mdata.metadata["magicc-version"]
        == "6.8.01 BETA, 7th July 2012 - live.magicc.org"
    )
    assert "__MAGICC 6.X DATA OUTPUT FILE__" in mdata.metadata["header"]
    assert (mdata.df.columns.get_level_values("TODO") == "N/A").all()
    assert (mdata.df.columns.get_level_values("UNITS") == "W/m^2").all()

    np.testing.assert_allclose(
        mdata.df["SOXB_RF", "N/A", "W/m^2", "GLOBAL"][1767], -0.00025099784
    )
    np.testing.assert_allclose(
        mdata.df["SOXB_RF", "N/A", "W/m^2", "GLOBAL"][1965], -0.032466593
    )
    np.testing.assert_allclose(
        mdata.df["SOXB_RF", "N/A", "W/m^2", "NHOCEAN"][1769], -0.0014779559
    )
    np.testing.assert_allclose(
        mdata.df["SOXB_RF", "N/A", "W/m^2", "SHOCEAN"][1820], -0.00039305876
    )
    np.testing.assert_allclose(
        mdata.df["SOXB_RF", "N/A", "W/m^2", "NHLAND"][2093], -0.024316933
    )
    np.testing.assert_allclose(mdata.df["SOXB_RF", "N/A", "W/m^2", "SHLAND"][1765], 0.0)


def test_load_out_slash_and_caret_in_heat_content_units():
    mdata = MAGICCData()
    mdata.read(TEST_OUT_DIR, "DAT_HEATCONTENT_AGGREG_DEPTH1.OUT")

    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "2018-09-23 18:33"
    assert (
        mdata.metadata["magicc-version"]
        == "6.8.01 BETA, 7th July 2012 - live.magicc.org"
    )
    assert "__MAGICC 6.X DATA OUTPUT FILE__" in mdata.metadata["header"]
    assert (mdata.df.columns.get_level_values("TODO") == "N/A").all()
    assert (mdata.df.columns.get_level_values("UNITS") == "10^22J").all()

    np.testing.assert_allclose(
        mdata.df["HEATCONTENT_AGGREG_DEPTH1", "N/A", "10^22J", "GLOBAL"][1767], 0.046263236
    )
    np.testing.assert_allclose(
        mdata.df["HEATCONTENT_AGGREG_DEPTH1", "N/A", "10^22J", "GLOBAL"][1965], 3.4193050
    )
    np.testing.assert_allclose(
        mdata.df["HEATCONTENT_AGGREG_DEPTH1", "N/A", "10^22J", "NHOCEAN"][1769], 0.067484257
    )
    np.testing.assert_allclose(
        mdata.df["HEATCONTENT_AGGREG_DEPTH1", "N/A", "10^22J", "SHOCEAN"][1820], -4.2688102
    )
    np.testing.assert_allclose(
        mdata.df["HEATCONTENT_AGGREG_DEPTH1", "N/A", "10^22J", "NHLAND"][2093], 0.0
    )
    np.testing.assert_allclose(mdata.df["HEATCONTENT_AGGREG_DEPTH1", "N/A", "10^22J", "SHLAND"][1765], 0.0)


def test_load_out_ocean_layers():
    mdata = MAGICCData()
    mdata.read(TEST_OUT_DIR, "TEMP_OCEANLAYERS.OUT")

    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "2018-09-23 18:33"
    assert (
        mdata.metadata["magicc-version"]
        == "6.8.01 BETA, 7th July 2012 - live.magicc.org"
    )
    assert (
        "__MAGICC 6.X TEMP_OCEANLAYERS DATA OUTPUT FILE__" in mdata.metadata["header"]
    )
    assert (mdata.df.columns.get_level_values("TODO") == "N/A").all()
    assert (mdata.df.columns.get_level_values("UNITS") == "K").all()

    np.testing.assert_allclose(
        mdata.df["OCEAN_TEMP_LAYER_001", "N/A", "K", "GLOBAL"][1765], 0.0
    )
    np.testing.assert_allclose(
        mdata.df["OCEAN_TEMP_LAYER_003", "N/A", "K", "GLOBAL"][1973], 0.10679213
    )
    np.testing.assert_allclose(
        mdata.df["OCEAN_TEMP_LAYER_050", "N/A", "K", "GLOBAL"][2100], 0.13890633
    )


def test_load_parameters_out_with_magicc_input():
    mdata = MAGICCData()
    test_file = "PARAMETERS.OUT"
    expected_error_msg = (
        r"^"
        + re.escape("MAGCCInput cannot read PARAMETERS.OUT as it is a config style file")
        + re.escape(", please use pymagicc.io.read_cfg_file")
        + r"$"
    )

    with pytest.raises(ValueError, match=expected_error_msg):
        mdata.read(TEST_OUT_DIR, test_file)


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


def test_load_prename():
    mdata = MAGICCData("HISTSSP_CO2I_EMIS.IN")
    mdata.read(TEST_DATA_DIR)

    assert (mdata.df.columns.get_level_values("UNITS") == "GtC").all()

    mdata.read(MAGICC6_DIR, "HISTRCP_CO2_CONC.IN")
    assert (mdata.df.columns.get_level_values("UNITS") == "ppm").all()
    assert not (mdata.df.columns.get_level_values("UNITS") == "GtC").any()


def test_direct_access():
    mdata = MAGICCData("HISTRCP_CO2I_EMIS.IN")
    mdata.read(MAGICC6_DIR)

    result = mdata["CO2I_EMIS", "R5LAM", 1983]
    expected = mdata.df.xs(
        ("CO2I_EMIS", "SET", "GtC", "R5LAM"),
        level=["VARIABLE", "TODO", "UNITS", "REGION"],
        axis=1,
        drop_level=False,
    ).loc[[1983]]
    pd.testing.assert_frame_equal(result, expected)

    result = mdata["CO2I_EMIS", "R5LAM"]
    expected = mdata.df.xs(
        ("CO2I_EMIS", "SET", "GtC", "R5LAM"),
        level=["VARIABLE", "TODO", "UNITS", "REGION"],
        axis=1,
        drop_level=False,
    )
    pd.testing.assert_frame_equal(result, expected)

    result = mdata["CO2I_EMIS"]
    expected = mdata.df.xs(
        ("CO2I_EMIS", "SET", "GtC", slice(None)),
        level=["VARIABLE", "TODO", "UNITS", "REGION"],
        axis=1,
        drop_level=False,
    )
    pd.testing.assert_frame_equal(result, expected)

    result = mdata[1994]
    expected = mdata.df.loc[[1994]]
    pd.testing.assert_frame_equal(result, expected)


def test_lazy_load():
    mdata = MAGICCData("HISTRCP_CO2I_EMIS.IN")
    # I don't know where the file is yet..
    with MAGICC6() as magicc:
        # and now load the data
        mdata.read(magicc.run_dir)
        assert mdata.df is not None


def test_proxy():
    mdata = MAGICCData("HISTRCP_CO2I_EMIS.IN")
    mdata.read(MAGICC6_DIR)

    # Get an attribute from the pandas DataFrame
    plot = mdata.plot
    assert plot.__module__ == "pandas.plotting._core"


def test_early_call():
    mdata = MAGICCData("HISTRCP_CO2I_EMIS.IN")

    with pytest.raises(ValueError):
        mdata["CO2I_EMIS"]["R5LAM"]

    with pytest.raises(ValueError):
        mdata.plot()


def test_no_name():
    mdata = MAGICCData()
    with pytest.raises(AssertionError):
        mdata.read("/tmp")


def test_invalid_name():
    mdata = MAGICCData()
    with pytest.raises(ValueError):
        mdata.read("/tmp", "MYNONEXISTANT.IN")


def test_default_path():
    mdata = MAGICCData("HISTRCP_CO2I_EMIS.IN")
    mdata.read()


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


@pytest.mark.parametrize("test_filename", [(None), ("test/filename.OUT")])
def test_magicc_input_init(test_filename):
    if test_filename is None:
        mdata = MAGICCData()
        assert mdata.filename is None
    else:
        mdata = MAGICCData(test_filename)
        assert mdata.filename is test_filename

    assert mdata.df is None
    assert mdata.metadata == {}


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
    "test_filename, expected_variable",
    [
        ("/test/filename/paths/HISTABCD_CH4_CONC.IN", "CH4_CONC"),
        ("test/filename.OUT", None),
    ],
)
def test_conc_in_reader_get_variable_from_filename(test_filename, expected_variable):

    conc_reader = _ConcInReader(test_filename)
    if expected_variable is None:
        expected_message = re.escape(
            "Cannot determine variable from filename: {}".format(test_filename)
        )
        with pytest.raises(ValueError, match=expected_message):
            conc_reader._get_variable_from_filename()
    else:
        assert conc_reader._get_variable_from_filename() == expected_variable


@pytest.fixture
def temp_file():
    temp_file = mkstemp()[1]
    yield temp_file
    print("deleting {}".format(temp_file))
    remove(temp_file)


@pytest.fixture
def temp_dir():
    temp_dir = mkdtemp()
    yield temp_dir
    print("deleting {}".format(temp_dir))
    rmtree(temp_dir)


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
def test_conc_in_file_read_write_functionally_identical(
    starting_fpath, starting_fname, confusing_metadata, temp_dir
):
    mi_writer = MAGICCData()
    mi_writer.read(filepath=starting_fpath, filename=starting_fname)

    mi_writer.write(join(temp_dir, starting_fname))

    mi_written = MAGICCData()
    mi_written.read(filepath=temp_dir, filename=starting_fname)

    mi_initial = MAGICCData()
    mi_initial.read(filepath=starting_fpath, filename=starting_fname)

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
        assert mi_written.metadata == mi_initial.metadata

    pd.testing.assert_frame_equal(mi_written.df, mi_initial.df)


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
        mdata.read(MAGICC6_DIR, file_to_read)


@pytest.mark.parametrize("file_to_read", [f for f in TEST_OUT_FILES])
def test_can_read_all_valid_files_in_magicc6_out_dir(file_to_read):
    if file_to_read.endswith(("PARAMETERS.OUT")):
        read_cfg_file(join(TEST_OUT_DIR, file_to_read))
    else:
        for p in INVALID_OUT_FILES:
            if re.match(p, file_to_read):
                return

        mdata = MAGICCData(file_to_read)
        mdata.read(TEST_OUT_DIR)


@pytest.mark.parametrize("file_to_read", [f for f in TEST_OUT_FILES])
def test_cant_read_all_invalid_files_in_magicc6_out_dir(file_to_read):
    valid_filename = True
    for p in INVALID_OUT_FILES:
        if re.match(p, file_to_read):
            valid_filename = False

    if valid_filename:
        return

    mdata = MAGICCData(file_to_read)
    if ("SUBANN" in file_to_read) or ("VOLCANIC_RF.BINOUT" in file_to_read):
        error_msg = (r"^.*" + re.escape(": Only annual binary files can currently be processed") + r".*$")
        with pytest.raises(InvalidTemporalResError, match=error_msg):
            mdata.read(TEST_OUT_DIR)
    else:
        error_msg = (r"^.*" + re.escape("is in an odd format for which we will never provide a reader/writer") + r".*$")
        with pytest.raises(NoReaderWriterError, match=error_msg):
            mdata.read(TEST_OUT_DIR)


@pytest.mark.parametrize("file_to_read", [f for f in listdir(TEST_OUT_DIR) if f.endswith('BINOUT') and f.startswith('DAT_')])
def test_bin_and_ascii_equal(file_to_read):
    try:
        mdata_bin = MAGICCData(file_to_read)
        mdata_bin.read(TEST_OUT_DIR)
    except InvalidTemporalResError:
        # Some BINOUT files are on a subannual time scale and cannot be read (yet)
        return

    assert (mdata_bin.df.columns.get_level_values("UNITS") == "unknown").all()
    assert (mdata_bin.df.columns.get_level_values("TODO") == "SET").all()

    mdata_ascii = MAGICCData(file_to_read.replace('BINOUT', 'OUT'))
    mdata_ascii.read(TEST_OUT_DIR)

    # There are some minor differences between in the dataframes due to availability of metadata in BINOUT files
    mdata_ascii.df.columns = mdata_ascii.df.columns.droplevel('UNITS').droplevel('TODO')
    mdata_bin.df.columns = mdata_bin.df.columns.droplevel('UNITS').droplevel('TODO')
    pd.testing.assert_frame_equal(mdata_ascii.df, mdata_bin.df)

# TODO add test of converting names for SCEN files
# TODO add test of valid output files e.g. checking namelists, formatting, column ordering etc.
