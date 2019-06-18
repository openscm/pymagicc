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

import numpy as np


class _MAGICCTimeConverter:
    def __init__(self):
        self._midmonths = None
        self._midmonths_magicc = None
        self._startmonths = None
        self._startmonths_magicc = None
        self._dummy_year_start = dt.datetime(2001, 1, 1)
        self._convert_to_decimal_required_precision = 4 * 10 ** -3

    @property
    def midmonths(self):
        if self._midmonths is None:
            self._midmonths = np.array(
                [self._calc_mid_month_year_frac(m) for m in range(1, 13)]
            )

        return self._midmonths

    @property
    def midmonths_magicc(self):
        if self._midmonths_magicc is None:
            self._midmonths_magicc = self.startmonths_magicc + 1 / 24
        return self._midmonths_magicc

    @property
    def startmonths(self):
        if self._startmonths is None:
            self._startmonths = np.array(
                [self._calc_start_month_year_frac(m) for m in range(1, 13)]
            )
        return self._startmonths

    @property
    def startmonths_magicc(self):
        if self._startmonths_magicc is None:
            self._startmonths_magicc = np.arange(0, 1, 1 / 12)
        return self._startmonths_magicc

    def _calc_start_month_year_frac(self, mth):
        total_s = self._calc_seconds_from_dummy_year_start(
            dt.datetime(self._dummy_year_start.year + 1, 1, 1)
        )

        start_month = (
            self._calc_seconds_from_dummy_year_start(
                dt.datetime(self._dummy_year_start.year, mth, 1)
            )
            / total_s
        )

        return start_month

    def _calc_mid_month_year_frac(self, mth):
        total_s = self._calc_seconds_from_dummy_year_start(
            dt.datetime(self._dummy_year_start.year + 1, 1, 1)
        )
        _, month_days = monthrange(self._dummy_year_start.year, mth)
        day_decimal = month_days * 0.5
        day = int(day_decimal)
        hour = int(day_decimal % 1 * 24)
        mid_month = (
            self._calc_seconds_from_dummy_year_start(
                dt.datetime(self._dummy_year_start.year, mth, day, hour)
            )
        ) / total_s

        return mid_month

    def _calc_seconds_from_dummy_year_start(self, dt_in):
        return (dt_in - self._dummy_year_start).total_seconds()

    def convert_to_datetime(self, decimal_year):
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

    def convert_to_decimal_year(self, idtime):
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
        if self._yr_frac_close_to(year_fraction, self.midmonths_magicc):
            decimal_bit = midmonth_decimal_bit
        elif self._yr_frac_close_to(year_fraction, self.midmonths):
            decimal_bit = midmonth_decimal_bit
        elif self._yr_frac_close_to(
            year_fraction, self.startmonths_magicc, must_be_greater=True
        ):
            decimal_bit = startmonth_decimal_bit
        elif self._yr_frac_close_to(
            year_fraction, self.startmonths, must_be_greater=True
        ):
            decimal_bit = startmonth_decimal_bit
        else:
            error_msg = "Your timestamps don't appear to be middle or start of month"
            raise ValueError(error_msg)

        return np.round(year + decimal_bit, 3)  # match MAGICC precision

    def _yr_frac_close_to(self, yfrac, other, must_be_greater=False):
        match_idx = np.where(
            np.abs(yfrac - other) < self._convert_to_decimal_required_precision
        )[0]
        if match_idx.size == 0:
            return False
        if must_be_greater and yfrac < other[match_idx]:
            return False
        return True


MAGICC_TIME_CONVERTER = _MAGICCTimeConverter()
