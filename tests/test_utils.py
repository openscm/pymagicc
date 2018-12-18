from os.path import join
from unittest.mock import patch
import warnings


import numpy as np
import pandas as pd
import pytest
import re


from pymagicc.io import MAGICCData
from pymagicc.utils import (
    apply_string_substitutions,
    join_timeseries,
    _join_timeseries_mdata,
)
from .conftest import MAGICC6_DIR, TEST_DATA_DIR, TEST_OUT_DIR


@patch("pymagicc.utils._compile_replacement_regexp")
@patch("pymagicc.utils._multiple_replace")
@patch("pymagicc.utils._check_unused_substitutions")
@patch("pymagicc.utils._check_duplicate_substitutions")
def test_apply_string_substitutions(
    mock_check_duplicate_substitutions,
    mock_check_unused_substitutions,
    mock_multiple_replace,
    mock_compile_replacement_regexp,
):
    treturn = "mocked return"
    mock_multiple_replace.return_value = treturn

    tcompiled_regexp = "mocked regexp"
    mock_compile_replacement_regexp.return_value = tcompiled_regexp

    tinput = "Hello JimBob"
    tsubstitutions = {"Jim": "Bob"}
    tcase_insensitive = "mocked case insensitivity"
    tunused_substitutions = "mocked unused substitutions"

    result = apply_string_substitutions(
        tinput,
        tsubstitutions,
        case_insensitive=tcase_insensitive,
        unused_substitutions=tunused_substitutions,
    )

    assert result == treturn

    mock_check_duplicate_substitutions.assert_called_with(tsubstitutions)
    mock_check_unused_substitutions.assert_called_with(
        tsubstitutions, tinput, tunused_substitutions, tcase_insensitive
    )
    mock_compile_replacement_regexp.assert_called_with(
        tsubstitutions, case_insensitive=tcase_insensitive
    )
    mock_multiple_replace.assert_called_with(tinput, tsubstitutions, tcompiled_regexp)


# would be ideal to have these come from docstring rather
# than being duplicated
@pytest.mark.parametrize(
    "inputs, substitutions, expected",
    [
        ("Hello JimBob", {"Jim": "Bob"}, "Hello BobBob"),
        (
            ["Hello JimBob", "Jim says, 'Hi Bob'"],
            {"Jim": "Bob"},
            ["Hello BobBob", "Bob says, 'Hi Bob'"],
        ),
        ("Muttons Butter", {"M": "B", "Button": "Zip"}, "Buttons Butter"),
        ("Muttons Butter", {"Mutton": "Gutter", "tt": "zz"}, "Gutters Buzzer"),
    ],
)
def test_apply_string_substitutions_default(inputs, substitutions, expected):
    result = apply_string_substitutions(inputs, substitutions)
    assert result == expected


@pytest.mark.parametrize(
    "inputs, substitutions, expected",
    [
        ("Hello JimBob", {"Jim": "Bob"}, "Hello JimJim"),
        (
            ["Hello JimBob", "Jim says, 'Hi Bob'"],
            {"Jim": "Bob"},
            ["Hello JimJim", "Jim says, 'Hi Jim'"],
        ),
    ],
)
def test_apply_string_substitutions_inverse(inputs, substitutions, expected):
    result = apply_string_substitutions(inputs, substitutions, inverse=True)
    assert result == expected


@pytest.mark.parametrize(
    "inputs, substitutions, expected", [("Butter", {"buTTer": "Gutter"}, "Gutter")]
)
def test_apply_string_substitutions_case_insensitive(inputs, substitutions, expected):
    result = apply_string_substitutions(inputs, substitutions, case_insensitive=True)
    assert result == expected


@pytest.mark.parametrize(
    "inputs, substitutions, unused_substitutions",
    [
        ("Butter", {"teeth": "tooth"}, "ignore"),
        ("Butter", {"teeth": "tooth"}, "warn"),
        ("Butter", {"teeth": "tooth"}, "raise"),
        ("Butter", {"teeth": "tooth"}, "junk"),
    ],
)
def test_apply_string_substitutions_unused_substitutions(
    inputs, substitutions, unused_substitutions
):
    if unused_substitutions == "ignore":
        result = apply_string_substitutions(
            inputs, substitutions, unused_substitutions=unused_substitutions
        )
        assert result == inputs
        return

    msg = "No substitution available for {'" + "{}".format(inputs) + "'}"
    if unused_substitutions == "warn":
        with warnings.catch_warnings(record=True) as warn_result:
            apply_string_substitutions(
                inputs, substitutions, unused_substitutions=unused_substitutions
            )

        assert len(warn_result) == 1
        assert str(warn_result[0].message) == msg
    elif unused_substitutions == "raise":
        with pytest.raises(ValueError, match=re.escape(msg)):
            apply_string_substitutions(
                inputs, substitutions, unused_substitutions=unused_substitutions
            )
    else:
        msg = re.escape("Invalid value for unused_substitutions, please see the docs")
        with pytest.raises(ValueError, match=msg):
            apply_string_substitutions(
                inputs, substitutions, unused_substitutions=unused_substitutions
            )


def test_apply_string_substitutions_duplicate_substitutions():
    # Note: we can ignore non case insensitive substitutions as if you try to generate
    # a dictionary with a duplicate key, it will just be overwritten
    assert {"teeth": "tooth", "teeth": "other"} == {"teeth": "other"}


@pytest.mark.parametrize(
    "inputs, substitutions, expected",
    [("teeth", {"teeth": "tooth", "Teeth": "tooth"}, "tooth")],
)
def test_apply_string_substitutions_duplicate_substitutions_case_insensitive(
    inputs, substitutions, expected
):
    res = apply_string_substitutions(inputs, substitutions)
    assert res == expected

    error_msg = re.escape(
        "Duplicate case insensitive substitutions: {}".format(substitutions)
    )
    with pytest.raises(ValueError, match=error_msg):
        apply_string_substitutions(inputs, substitutions, case_insensitive=True)


# integration test
def test_join_timeseries():
    mdata = MAGICCData()
    mdata.read(join(TEST_DATA_DIR, "RCP3PD_EMISSIONS.DAT"))
    base = mdata.df.copy()
    base["todo"] = "SET"

    mdata.read(join(TEST_DATA_DIR, "RCP60.SCEN"))
    scen = mdata.df.copy()

    res = join_timeseries(base=base, overwrite=scen, harmonise_linear=[2005, 2012])

    row = (
        (res.df["variable"] == "Emissions|CO2|MAGICC Fossil and Industrial")
        & (res.df["region"] == "World")
        & (res.df["time"] == 2000)
        & (res.df["unit"] == "Gt C / yr")
        & (res.df["todo"] == "SET")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(res.df[row].value, 6.735)

    row = (
        (res.df["variable"] == "Emissions|CO2|MAGICC Fossil and Industrial")
        & (res.df["region"] == "World")
        & (res.df["time"] == 2008)
        & (res.df["unit"] == "Gt C / yr")
        & (res.df["todo"] == "SET")
    )
    assert sum(row) == 1
    val_2012 = 8.5115 + (8.5904 - 8.115) * 2 / 10
    expected = (val_2012 - 7.971) / 7 * 3
    np.testing.assert_allclose(res.df[row].value, expected)

    row = (
        (res.df["variable"] == "Emissions|CO2|MAGICC Fossil and Industrial")
        & (res.df["region"] == "World")
        & (res.df["time"] == 2015)
        & (res.df["unit"] == "Gt C / yr")
        & (res.df["todo"] == "SET")
    )
    assert sum(row) == 1
    expected = 8.5115 + (8.5904 - 8.115) / 2
    np.testing.assert_allclose(res.df[row].value, expected)

    row = (
        (res.df["variable"] == "Emissions|CFC11")
        & (res.df["region"] == "World")
        & (res.df["time"] == 1995)
        & (res.df["unit"] == "kt CFC11 / yr")
        & (res.df["todo"] == "SET")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(res.df[row].value, 119.235)

    row = (
        (res.df["variable"] == "Emissions|CFC11")
        & (res.df["region"] == "World")
        & (res.df["time"] == 2015)
        & (res.df["unit"] == "kt CFC11 / yr")
        & (res.df["todo"] == "SET")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(res.df[row].value, 494.9)


@patch.object("pymagicc.utils._MAGICCData", "df")
@patch("pymagicc.utils._join_timeseries_mdata")
def test_join_timeseries_unit(mock_join_timeseries_mdata, mock_magicc_data_df):
    tbase = "mocked"
    toverwrite = "also mocked"
    tdf = "mocked as well"
    toutput = "mocked output"

    mock_magicc_data_df.return_value = tdf
    mock_join_timeseries_mdata.return_value = toutput

    res = join_timeseries(base=tbase, overwrite=toverwrite)

    assert res == toutput

    mock_join_timeseries_mdata.assert_called_with(
        base=tdf, overwrite=tdf, harmonise_linear=None
    )


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
    base_df = MAGICCData()
    base_df.df = bdf

    yield base_df


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
    overwrite_df = MAGICCData()
    overwrite_df.df = odf

    yield overwrite_df


def test_join_timeseries_mdata_no_harmonisation(join_base_df, join_overwrite_df):
    res = _join_timeseries_mdata(
        base=join_base_df, overwrite=join_overwrite_df, harmonise_linear=None
    )

    row = (
        (res.df["variable"] == "Emissions|CO2")
        & (res.df["region"] == "World")
        & (res.df["time"] == 2005)
        & (res.df["unit"] == "GtC/yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(res.df[row].value, 1.5)

    row = (
        (res.df["variable"] == "Emissions|CO2")
        & (res.df["region"] == "World")
        & (res.df["time"] == 2015)
        & (res.df["unit"] == "GtC/yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(res.df[row].value, 1.0)

    row = (
        (res.df["variable"] == "Emissions|CO2")
        & (res.df["region"] == "World")
        & (res.df["time"] == 2020)
        & (res.df["unit"] == "GtC/yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(res.df[row].value, 1 + (2 - 1) / 35 * 5)

    row = (
        (res.df["variable"] == "Emissions|CH4")
        & (res.df["region"] == "World")
        & (res.df["time"] == 2020)
        & (res.df["unit"] == "MtCH4/yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(res.df[row].value, 1.3)

    row = (
        (res.df["variable"] == "Emissions|CH4")
        & (res.df["region"] == "World")
        & (res.df["time"] == 2100)
        & (res.df["unit"] == "MtCH4/yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(res.df[row].value, 1.3)

    assert False


def test_join_timeseries_mdata_harmonisation(join_base_df, join_overwrite_df):
    res = _join_timeseries_mdata(
        base=join_base_df, overwrite=join_overwrite_df, harmonise_linear=[2010, 2020]
    )

    row = (
        (res.df["variable"] == "Emissions|CO2")
        & (res.df["region"] == "World")
        & (res.df["time"] == 2012)
        & (res.df["unit"] == "GtC/yr")
    )
    assert sum(row) == 1
    overwrite_co2_val_2020 = 1 + (2 - 1) / 35 * 5
    expected = 2 + (overwrite_co2_val_2020 - 2) / 10 * 2
    np.testing.assert_allclose(res.df[row].value, expected)

    row = (
        (res.df["variable"] == "Emissions|CO2")
        & (res.df["region"] == "World")
        & (res.df["time"] == 2050)
        & (res.df["unit"] == "GtC/yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(res.df[row].value, 2.0)

    row = (
        (res.df["variable"] == "Emissions|CH4")
        & (res.df["region"] == "World")
        & (res.df["time"] == 2020)
        & (res.df["unit"] == "MtCH4/yr")
    )
    assert sum(row) == 1
    np.testing.assert_allclose(res.df[row].value, 1.3)

    assert False


def test_join_timeseries_mdata_harmonisation_errors(join_base_df, join_overwrite_df):
    error_msg = re.escape("Harmonisation start year is after end of base timeseries")
    with pytest.raises(ValueError, match=error_msg):
        _join_timeseries_mdata(
            base=join_base_df,
            overwrite=join_overwrite_df,
            harmonise_linear=[2025, 2030],
        )

    error_msg = re.escape(
        "Harmonisation end year is before start of overwrite timeseries"
    )
    with pytest.raises(ValueError, match=error_msg):
        _join_timeseries_mdata(
            base=join_base_df,
            overwrite=join_overwrite_df,
            harmonise_linear=[2005, 2010],
        )

    join_base_df.df = join_base_df.df[join_base_df.df["variable"] == "Emissions|CH4"]
    error_msg = re.escape("No overlapping indices")
    with pytest.raises(ValueError, match=error_msg):
        _join_timeseries_mdata(base=join_base_df, overwrite=join_overwrite_df)

    assert False


# TODO: improve join timeseries so it can also handle datetimes in the time axis
