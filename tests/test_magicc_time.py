import datetime as dt

import numpy as np
import pytest

from pymagicc.magicc_time import convert_to_datetime, convert_to_decimal_year


@pytest.mark.parametrize(
    "spoint,output",
    (
        [2010.0, dt.datetime(2010, 1, 1, 1)],
        [1913 + 1 / 24, dt.datetime(1913, 1, 15, 12)],
        [1998 + 1 / 12, dt.datetime(1998, 2, 1, 1)],
        [1998 + 1.9 / 24, dt.datetime(1998, 2, 1, 1)],
    ),
)
def test_convert_to_datetime(spoint, output):
    res = convert_to_datetime(spoint)
    assert res == output


@pytest.mark.parametrize(
    "spoint", (2010.06, 1913 + 1.5 / 24, 1998 + 1.25 / 12, 1998 + 1.7 / 24)
)
def test_convert_to_datetime_error(spoint):
    error_msg = "Your timestamps don't appear to be middle or start of month"
    with pytest.raises(ValueError, match=error_msg):
        convert_to_datetime(spoint)


@pytest.mark.parametrize(
    "spoint,output",
    (
        [dt.datetime(2010, 1, 1, 1), 2010.0],
        [dt.datetime(1913, 1, 15, 12), 1913 + 1 / 24],
        [dt.datetime(1998, 2, 1, 1), 1998 + 1 / 12],
        [dt.datetime(2156, 12, 1, 1), 2156 + 11 / 12],
        [dt.datetime(2000, 1, 15, 1), 2000 + 1 / 24],
    ),
)
def test_convert_to_decimal_year(spoint, output):
    res = convert_to_decimal_year(spoint)
    assert np.round(res, 3) == np.round(output, 3)


@pytest.mark.parametrize(
    "spoint",
    (
        dt.datetime(2010, 1, 5),
        dt.datetime(1913, 1, 20),
        dt.datetime(1998, 2, 28),
        dt.datetime(1998, 12, 31),
    ),
)
def test_convert_to_decimal_year_error(spoint):
    error_msg = "Your timestamps don't appear to be middle or start of month"
    with pytest.raises(ValueError, match=error_msg):
        convert_to_decimal_year(spoint)
