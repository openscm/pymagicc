"""
Handling of conversion from datetime to MAGICC's internal time conventions and back.

Internally, MAGICC effectively operates on a monthly calendar, where each year is
comprised of 12 equally sized months. This convention means that we have to be a bit
careful when moving back and forth between datetimes and MAGICC's time conventions.
However, we also want Pymagicc to be a little bit flexible and smart about how it
handles these conversions. As a result, we must interpret 'middle of the month' and
'start of the month' rather than strictly defining them. This module defines these
interpretations
"""
import datetime as dt
from calendar import monthrange
from functools import lru_cache

import numpy as np

_convert_to_decimal_required_precision = 4 * 10 ** -3
"""Maximum relative deviation between float times before they are considered unequal"""

_startmonths_magicc = np.arange(0, 1, 1 / 12)
_midmonths_magicc = _startmonths_magicc + 1 / 24

_dummy_year_start = dt.datetime(2001, 1, 1)


def _calc_seconds_from_dummy_year_start(dt_in):
    return (dt_in - _dummy_year_start).total_seconds()


def _calc_start_month_year_frac(mth):
    total_s = _calc_seconds_from_dummy_year_start(
        dt.datetime(_dummy_year_start.year + 1, 1, 1)
    )

    start_month = (
        _calc_seconds_from_dummy_year_start(dt.datetime(_dummy_year_start.year, mth, 1))
        / total_s
    )

    return start_month


def _calc_mid_month_year_frac(mth):
    total_s = _calc_seconds_from_dummy_year_start(
        dt.datetime(_dummy_year_start.year + 1, 1, 1)
    )
    _, month_days = monthrange(_dummy_year_start.year, mth)
    day_decimal = month_days * 0.5
    day = int(day_decimal)
    hour = int(day_decimal % 1 * 24)
    mid_month = (
        _calc_seconds_from_dummy_year_start(
            dt.datetime(_dummy_year_start.year, mth, day, hour)
        )
    ) / total_s

    return mid_month


_startmonths = np.array([_calc_start_month_year_frac(m) for m in range(1, 13)])
_midmonths = np.array([_calc_mid_month_year_frac(m) for m in range(1, 13)])


@lru_cache(maxsize=128)
def convert_to_datetime(decimal_year):
    """
    Convert a decimal year from MAGICC to a datetime

    Parameters
    ----------
    decimal_year : float
        Time point to convert

    Returns
    -------
    :obj:`datetime.datetime`
        Datetime representation of MAGICC's decimal year

    Raises
    ------
    ValueError
        If we are not confident that the input times follow MAGICC's internal time
        conventions (i.e. are not start or middle of the month).
    """
    # MAGICC dates are to nearest month at most precise
    year = int(decimal_year)
    month_decimal = decimal_year % 1 * 12
    month_fraction = month_decimal % 1
    # decide if start, middle or end of month
    if month_fraction > 0.9:
        # MAGICC is never actually end of month, this case is just due to
        # rounding errors. e.g. in MAGICC, 1000.083 is year 1000, start of
        # February, but, for February, decimal_year % 1 * 12 = 0.083 * 12
        # = 0.996. Hence to get the right month, i.e. February, we need to add 1
        # to the month after rounding.
        month = int(np.ceil(month_decimal)) + 1
        day = 1
        hour = 1
    elif np.round(month_fraction, 1) == 0.5:
        # middle of month
        month = int(np.ceil(month_decimal))
        _, month_days = monthrange(year, month)
        day_decimal = month_days * 0.5
        day = int(day_decimal)
        hour = int(day_decimal % 1 * 24)
    elif np.round(month_fraction, 1) == 0:
        # start of month
        month = int(month_decimal) + 1
        day = 1
        hour = 1
    else:
        error_msg = "Your timestamps don't appear to be middle or start of month"
        raise ValueError(error_msg)

    res = dt.datetime(year, month, day, hour)
    return res


@lru_cache(maxsize=128)
def convert_to_decimal_year(idtime):
    """
    Convert a datetime to MAGICC's expected decimal year representation

    Parameters
    ----------
    idtime : :obj:`datetime.datetime`
        :obj:`datetime.datetime` instance to convert to MAGICC's internal decimal
        year conventions

    Returns
    -------
    float
        MAGICC's internal decimal year representation of ``idtime``

    Raises
    ------
    ValueError
        If we are not confident about how to convert the input times so that they
        follow MAGICC's internal time conventions (i.e. we are not sure if
        ``idtime`` is start or middle of the month).
    """
    year = idtime.year
    month = idtime.month
    year_fraction = (idtime - dt.datetime(year, 1, 1)).total_seconds() / (
        dt.datetime(year + 1, 1, 1) - dt.datetime(year, 1, 1)
    ).total_seconds()

    midmonth_decimal_bit = ((month - 1) * 2 + 1) / 24
    startmonth_decimal_bit = (month - 1) / 12
    if _yr_frac_close_to(year_fraction, _midmonths_magicc):
        decimal_bit = midmonth_decimal_bit
    elif _yr_frac_close_to(year_fraction, _midmonths):
        decimal_bit = midmonth_decimal_bit
    elif _yr_frac_close_to(year_fraction, _startmonths_magicc, must_be_greater=True):
        decimal_bit = startmonth_decimal_bit
    elif _yr_frac_close_to(year_fraction, _startmonths, must_be_greater=True):
        decimal_bit = startmonth_decimal_bit
    else:
        error_msg = "Your timestamps don't appear to be middle or start of month"
        raise ValueError(error_msg)

    return np.round(year + decimal_bit, 3)  # match MAGICC precision


def _yr_frac_close_to(yfrac, other, must_be_greater=False):
    match_idx = np.where(
        np.abs(yfrac - other) < _convert_to_decimal_required_precision
    )[0]
    if match_idx.size == 0:
        return False
    if must_be_greater and yfrac < other[match_idx]:
        return False
    return True


def _adjust_df_index_to_match_timeseries_type(df, ttype):
    """
    Adjust a df's index to reflect the underlying timeseries type

    Parameters
    ----------
    df : :obj:`pd.DataFrame`
        Dataframe to adjust

    ttype : str
        String indicating the kind of data in the file (look at the sample .MAG
        file for explanation of the types in detail)

    Returns
    -------
    :obj:`pd.DataFrame`
        Dataframe with times adjusted to match with ``ttype``
    """
    if ttype in ("POINT_START_YEAR", "AVERAGE_YEAR_START_YEAR"):
        df.index = df.index.map(lambda x: dt.datetime(x, 1, 1))
        return df

    if ttype in ("POINT_MID_YEAR", "AVERAGE_YEAR_MID_YEAR"):
        df.index = df.index.map(lambda x: dt.datetime(x, 7, 1))
        return df

    if ttype in ("POINT_END_YEAR", "AVERAGE_YEAR_END_YEAR"):
        df.index = df.index.map(lambda x: dt.datetime(x, 12, 31))
        return df

    if ttype in ("MONTHLY",):
        df.index = df.index.map(convert_to_datetime)
        return df

    raise AssertionError("Unrecognised `ttype`: {}".format(ttype))  # pragma: no cover
