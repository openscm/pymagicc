from datetime import datetime
from calendar import monthrange


import pandas as pd
import numpy as np
from pyam import IamDataFrame


class OpenSCMDataFrame(IamDataFrame):
    def __init__(self, data):
        if isinstance(data, pd.DataFrame) or isinstance(data, pd.Series):
            if "time" in data.columns:
                # hack around automatic conversion to datetime column in pandas which
                # blows up with climate data as datetime is nanosecond resolution and
                # span we want can't be stored
                # TODO: find issue that relates to this
                time = data["time"].copy()
                data = data.rename({"time": "year"}, axis="columns")
                data["year"] = 1212
                super().__init__(data)
                self.data = self.data.drop("year", axis="columns")
                self.data["time"] = _check_time(time).values
                self.time_col = "time"
            else:
                super().__init__(data)
        else:
            super().__init__(data)


def _check_time(time_srs):
    if type(time_srs.iloc[0]) == pd._libs.tslibs.timestamps.Timestamp:
        pass
    elif time_srs.iloc[0].dtype <= np.int:
        # years, put in middle of year
        time_srs = time_srs.apply(lambda x: datetime(x, 7, 12))
    else:
        # decimal years
        def _convert_to_datetime(decimal_year):
            # MAGICC dates are to nearest month at most precise
            year = int(decimal_year)
            month_decimal = decimal_year % 1 * 12
            month_fraction = month_decimal % 1
            # decide if start, middle or end of month
            if np.round(month_fraction, 1) == 1:
                # MAGICC is never actually end of month, this case is just due to
                # rounding errors. E.g. in MAGICC, 1000.083 is year 1000, start of
                # February, but 0.083 * 12 = 0.96. Hence to get the right month,
                # i.e. February, after rounding down we need the + 2 below.
                month = int(month_decimal) + 2
                day = 1
                hour = 1
                month += 1
            elif np.round(month_fraction, 1) == 0.5:
                month = int(np.ceil(month_decimal))
                _, month_days = monthrange(year, month)
                day_decimal = month_days*0.5
                day = int(day_decimal)
                hour = int(day_decimal % 1 * 24)
            elif np.round(month_fraction, 1) == 0:
                month = int(month_decimal) + 1
                day = 1
                hour = 1
            else:
                error_msg = (
                    "Your timestamps don't appear to be middle or start of month"
                )
                raise ValueError(error_msg)

            res = datetime(year, month, day, hour)
            return res

        time_srs = time_srs.apply(lambda x: _convert_to_datetime(x))

    return time_srs
