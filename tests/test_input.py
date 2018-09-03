from os import remove
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
from pymagicc.input import MAGICCInput, InputReader, ConcInReader, ScenWriter

MAGICC6_DIR = pkg_resources.resource_filename("pymagicc", "MAGICC6/run")
MAGICC7_DIR = join(dirname(__file__), "test_data")

# TEMPCHANGELOG:
# - stop reading in the nml. All the values in it should be introspected hence this step is redundant. If required as a check of file validity in future, we can write a separate function, it shouldn't be in the reader

# TODO:
# - write tests for SCEN and SCEN7 files
# - add read/write identical tests


def generic_mdata_tests(mdata):
    assert mdata.is_loaded == True
    assert isinstance(mdata.df, pd.DataFrame)
    assert mdata.df.index.names == ["YEAR"]
    assert mdata.df.columns.names == ["VARIABLE", "TODO", "UNITS", "REGION"]
    for key in ["units", "firstdatarow", "dattype"]:
        with pytest.raises(KeyError):
            mdata.metadata[key]
    assert isinstance(mdata.metadata["header"], str)


def test_load_magicc6_emis():
    mdata = MAGICCInput()
    assert mdata.is_loaded == False
    mdata.read(MAGICC6_DIR, "HISTRCP_CO2I_EMIS.IN")
    generic_mdata_tests(mdata)

    np.testing.assert_allclose(
        mdata.df["CO2I_EMIS", "SET", "GtC", "R5ASIA"][2000], 1.7682027e+000
    )


def test_load_magicc6_conc():
    mdata = MAGICCInput()
    mdata.read(MAGICC6_DIR, "HISTRCP_CO2_CONC.IN")

    assert (mdata.df.columns.get_level_values("UNITS") == "ppm").all()
    generic_mdata_tests(mdata)
    np.testing.assert_allclose(
        mdata.df["CO2_CONC", "SET", "ppm", "GLOBAL"][1048], 2.80435733e+002
    )

# test for file with magiccc6 style vars in filename
# test for file with special characters e.g. umlauts

def test_load_magicc7_emis():
    mdata = MAGICCInput()
    mdata.read(MAGICC7_DIR, "HISTSSP_CO2I_EMIS.IN")

    generic_mdata_tests(mdata)

    assert (
        mdata.metadata["contact"]
        == "Zebedee Nicholls, Australian-German Climate and Energy College, University of Melbourne, zebedee.nicholls@climate-energy-college.org"
    )
    assert (mdata.df.columns.get_level_values("UNITS") == "GtC").all()
    # change read in to CO2I_EMIS
    np.testing.assert_allclose(mdata.df["CO2I", "SET", "GtC", "R6REF"][2013], 0.6638)
    np.testing.assert_allclose(mdata.df["CO2I", "SET", "GtC", "R6ASIA"][2000], 1.6911)

def test_load_ot():
    mdata = MAGICCInput()
    mdata.read(MAGICC6_DIR, "MIXED_NOXI_OT.IN")

    generic_mdata_tests(mdata)

    assert mdata.metadata["data"] == "Optical Thickness"
    assert mdata.metadata["description"] == "the land/ocean ratio of optical depth of NOXI is scaled with the hemispheric EDGAR NOXI emissions. NOXI opt. depth as available on http://www.giss.nasa.gov/data/simodel/trop.aer/"
    assert mdata.metadata["source"] == "Mixed: EDGAR: www.mnp.nl; NASA-GISS: http://data.giss.nasa.gov/"
    assert mdata.metadata["compiled by"] == "Malte Meinshausen, Lauder NZ, NCAR/PIK, malte.meinshausen@gmail.com"
    assert mdata.metadata["date"] == "18-Jul-2006 11:02:48"
    assert mdata.metadata["unit normalisation"] == "Normalized to 1 in year 2000"

    assert (mdata.df.columns.get_level_values("UNITS") == "DIMENSIONLESS").all()
    assert (mdata.df.columns.get_level_values("TODO") == "SET").all()
    assert (mdata.df.columns.get_level_values("VARIABLE") == "NOX_RF").all()

    np.testing.assert_allclose(mdata.df["NOX_RF", "SET", "DIMENSIONLESS", "NHOCEAN"][1765], 0.00668115649)
    np.testing.assert_allclose(mdata.df["NOX_RF", "SET", "DIMENSIONLESS", "NHLAND"][1865], 0.526135104)
    np.testing.assert_allclose(mdata.df["NOX_RF", "SET", "DIMENSIONLESS", "SHOCEAN"][1965], 0.612718845)
    np.testing.assert_allclose(mdata.df["NOX_RF", "SET", "DIMENSIONLESS", "SHLAND"][2000], 3.70377980)


def test_load_scen():
    mdata = MAGICCInput()
    mdata.read(MAGICC6_DIR, "RCP26.SCEN")

    generic_mdata_tests(mdata)

    assert (
        mdata.metadata["date"]
        == "26/11/2009 11:29:06; MAGICC-VERSION: 6.3.09, 25 November 2009"
    )
    assert "Final RCP3PD with constant emissions" in mdata.metadata["header"]

    np.testing.assert_allclose(mdata.df["CO2I", "SET", "GtC", "WORLD"][2000], 6.7350)
    np.testing.assert_allclose(mdata.df["N2O", "SET", "MtN2O-N", "WORLD"][2002], 7.5487)
    np.testing.assert_allclose(mdata.df["HFC4310", "SET", "kt", "WORLD"][2001], 0.6470)
    np.testing.assert_allclose(mdata.df["SOX", "SET", "MtS", "R5OECD"][2005], 11.9769)
    np.testing.assert_allclose(mdata.df["NMVOC", "SET", "Mt", "R5OECD"][2050], 18.2123)
    np.testing.assert_allclose(mdata.df["HFC23", "SET", "kt", "R5REF"][2100], 0.0)
    np.testing.assert_allclose(mdata.df["HFC125", "SET", "kt", "R5REF"][2125], 5.2133)
    np.testing.assert_allclose(
        mdata.df["HFC143A", "SET", "kt", "R5ASIA"][2040], 33.3635
    )
    np.testing.assert_allclose(mdata.df["SF6", "SET", "kt", "R5ASIA"][2040], 0.8246)
    np.testing.assert_allclose(mdata.df["CO2B", "SET", "GtC", "R5MAF"][2050], -0.0125)
    np.testing.assert_allclose(mdata.df["CH4", "SET", "MtCH4", "R5MAF"][2070], 37.6218)
    np.testing.assert_allclose(mdata.df["NOX", "SET", "MtN", "R5LAM"][2080], 1.8693)
    np.testing.assert_allclose(mdata.df["BC", "SET", "Mt", "R5LAM"][2090], 0.4254)
    np.testing.assert_allclose(mdata.df["NH3", "SET", "MtN", "BUNKERS"][2000], 0.0)
    np.testing.assert_allclose(mdata.df["SF6", "SET", "kt", "BUNKERS"][2002], 0.0)


def test_load_scen_sres():
    mdata = MAGICCInput()
    mdata.read(MAGICC6_DIR, "SRESA1B.SCEN")

    generic_mdata_tests(mdata)

    assert "Antero Hot Springs" in mdata.metadata["header"]

    np.testing.assert_allclose(mdata.df["CO2I", "SET", "GtC", "WORLD"][2000], 6.8963)
    np.testing.assert_allclose(mdata.df["N2O", "SET", "MtN2O-N", "WORLD"][1990], 6.6751)
    np.testing.assert_allclose(mdata.df["HFC4310", "SET", "kt", "WORLD"][2000], 0.0000)
    np.testing.assert_allclose(mdata.df["SOX", "SET", "MtS", "OECD90"][2010], 9.8762)
    np.testing.assert_allclose(mdata.df["NMVOC", "SET", "Mt", "OECD90"][2050], 28.1940)
    np.testing.assert_allclose(mdata.df["HFC23", "SET", "kt", "REF"][2100], 0.0624)
    np.testing.assert_allclose(mdata.df["HFC125", "SET", "kt", "REF"][2100], 5.4067)
    np.testing.assert_allclose(mdata.df["HFC143A", "SET", "kt", "ASIA"][2040], 15.4296)
    np.testing.assert_allclose(mdata.df["SF6", "SET", "kt", "ASIA"][2040], 6.4001)
    np.testing.assert_allclose(mdata.df["CO2B", "SET", "GtC", "ALM"][2050], 0.2613)
    np.testing.assert_allclose(mdata.df["CH4", "SET", "MtCH4", "ALM"][2070], 130.1256)


def test_load_scen7():
    mdata = MAGICCInput()
    mdata.read(MAGICC7_DIR, "TESTSCEN7.SCEN7")

    generic_mdata_tests(mdata)

    assert mdata.metadata["date"] == "13-Oct-2017 16:45:35"
    assert mdata.metadata["description"] == "TEST SCEN7 file"
    assert "NOTES" in mdata.metadata["header"]
    assert "~~~~~" in mdata.metadata["header"]
    assert "Some notes" in mdata.metadata["header"]

    np.testing.assert_allclose(mdata.df["CO2I", "SET", "GtC", "WORLD"][2000], 6.7350)
    np.testing.assert_allclose(
        mdata.df["N2OI", "SET", "MtN2O-N", "WORLD"][2002], 7.5487
    )
    np.testing.assert_allclose(mdata.df["HFC23", "SET", "kt", "WORLD"][2001], 10.4328)
    np.testing.assert_allclose(mdata.df["SOX", "SET", "MtS", "R6OECD90"][2005], 11.9769)
    np.testing.assert_allclose(
        mdata.df["NMVOC", "SET", "Mt", "R6OECD90"][2050], 18.2123
    )
    np.testing.assert_allclose(mdata.df["HFC23", "SET", "kt", "R6REF"][2100], 0.0)
    np.testing.assert_allclose(mdata.df["CH2Cl2", "SET", "kt", "R6REF"][2125], 5.2133)
    np.testing.assert_allclose(
        mdata.df["HFC143A", "SET", "kt", "R6ASIA"][2040], 33.3635
    )
    np.testing.assert_allclose(mdata.df["SO2F2", "SET", "kt", "R6ASIA"][2040], 0.8246)
    np.testing.assert_allclose(mdata.df["CO2B", "SET", "GtC", "R6MAF"][2050], -0.0125)
    np.testing.assert_allclose(mdata.df["CH4", "SET", "MtCH4", "R6MAF"][2070], 37.6218)
    np.testing.assert_allclose(mdata.df["NOX", "SET", "MtN", "R6LAM"][2080], 1.8693)
    np.testing.assert_allclose(mdata.df["BCB", "SET", "Mt", "R6LAM"][2090], 0.4254)
    np.testing.assert_allclose(mdata.df["NH3", "SET", "MtN", "BUNKERS"][2000], 0.0)
    np.testing.assert_allclose(mdata.df["SO2F2", "SET", "kt", "BUNKERS"][2002], 0.0)


def test_load_prename():
    mdata = MAGICCInput("HISTSSP_CO2I_EMIS.IN")
    mdata.read(MAGICC7_DIR)

    assert (mdata.df.columns.get_level_values("UNITS") == "GtC").all()

    mdata.read(MAGICC6_DIR, "HISTRCP_CO2_CONC.IN")
    assert (mdata.df.columns.get_level_values("UNITS") == "ppm").all()
    assert not (mdata.df.columns.get_level_values("UNITS") == "GtC").any()


def test_direct_access():
    mdata = MAGICCInput("HISTRCP_CO2I_EMIS.IN")
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
    mdata = MAGICCInput("HISTRCP_CO2I_EMIS.IN")
    # I don't know where the file is yet..
    with MAGICC6() as magicc:
        # and now load the data
        mdata.read(magicc.run_dir)
        assert mdata.df is not None


def test_proxy():
    mdata = MAGICCInput("HISTRCP_CO2I_EMIS.IN")
    mdata.read(MAGICC6_DIR)

    # Get an attribute from the pandas DataFrame
    plot = mdata.plot
    assert plot.__module__ == "pandas.plotting._core"


def test_early_call():
    mdata = MAGICCInput("HISTRCP_CO2I_EMIS.IN")

    with pytest.raises(ValueError):
        mdata["CO2I"]["R5LAM"]

    with pytest.raises(ValueError):
        mdata.plot()


def test_no_name():
    mdata = MAGICCInput()
    with pytest.raises(AssertionError):
        mdata.read("/tmp")


def test_invalid_name():
    mdata = MAGICCInput()
    with pytest.raises(ValueError):
        mdata.read("/tmp", "MYNONEXISTANT.IN")


def test_default_path():
    mdata = MAGICCInput("HISTRCP_CO2I_EMIS.IN")
    mdata.read()


def test_header_metadata():
    m = InputReader("test")
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

    m = InputReader("test")
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
def test_MAGICCInput_init(test_filename):
    if test_filename is None:
        mdata = MAGICCInput()
        assert mdata.filename is None
    else:
        mdata = MAGICCInput(test_filename)
        assert mdata.filename is test_filename

    assert mdata.df is None
    assert mdata.metadata == {}


def test_set_lines():
    reader = InputReader("test")
    with pytest.raises(FileNotFoundError):
        reader._set_lines()

    test_file = join(MAGICC7_DIR, "HISTSSP_CO2I_EMIS.IN")
    assert isfile(test_file)

    reader = InputReader(test_file)
    reader._set_lines()
    with open(test_file) as f:
        assert reader.lines == f.readlines()


@pytest.mark.parametrize(
    "test_filename, expected_variable",
    [
        ("/test/filename/paths/HISTABCD_CH4_CONC.IN", "CH4_CONC"),
        ("test/filename.OUT", None),
    ],
)
def test_CONC_INReader_get_variable_from_filename(test_filename, expected_variable):

    conc_reader = ConcInReader(test_filename)
    if expected_variable is None:
        expected_message = re.escape(
            "Cannot determine variable from filename: {}".format(test_filename)
        )
        with pytest.raises(SyntaxError, match=expected_message):
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
        (MAGICC6_DIR, "HISTRCP_CO2_CONC.IN", False),
        (MAGICC6_DIR, "HISTRCP_CO2I_EMIS.IN", False),
        (MAGICC6_DIR, "MIXED_NOXI_OT.IN", True),  # handling of units and gas is super weird
        (MAGICC6_DIR, "RCP26.SCEN", True),  # metadata all over the place
        (MAGICC7_DIR, "HISTSSP_CO2I_EMIS.IN", False),
        (MAGICC7_DIR, "TESTSCEN7.SCEN7", False),
    ],
)
def test_conc_in_file_read_write_functionally_identical(
    starting_fpath, starting_fname, confusing_metadata, temp_dir
):
    mi_writer = MAGICCInput()
    mi_writer.read(filepath=starting_fpath, filename=starting_fname)

    mi_writer.write(join(temp_dir, starting_fname))

    mi_written = MAGICCInput()
    mi_written.read(filepath=temp_dir, filename=starting_fname)

    mi_initial = MAGICCInput()
    mi_initial.read(filepath=starting_fpath, filename=starting_fname)

    if not starting_fname.endswith(".SCEN"):
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
    writer = ScenWriter()
    if expected == "unrecognised regions":
        error_msg = "Could not determine scen special code for regions {}".format(
            regions
        )
        error_msg = r"potato"
        with pytest.raises(ValueError, message=error_msg):
            writer._get_special_scen_code(regions, emissions)
    elif expected == "unrecognised emissions":
        error_msg = "Could not determine scen special code for emissions {}".format(
            emissions
        )
        error_msg = r"potato"
        with pytest.raises(ValueError, message=error_msg):
            writer._get_special_scen_code(regions, emissions)
    else:
        result = writer._get_special_scen_code(regions, emissions)
        assert result == expected


# add test of converting names for SCEN files
# add test of valid output files e.g. checking namelists, formatting, column ordering etc.
