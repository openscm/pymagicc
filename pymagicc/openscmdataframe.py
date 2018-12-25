from datetime import datetime


import pandas as pd
from pyam import IamDataFrame


class OpenSCMDataFrame(IamDataFrame):
    def __init__(self, data):
        if isinstance(data, pd.DataFrame) or isinstance(data, pd.Series):
            if "time" in data.columns:
                # hack around automatic conversion to datetime column in pandas which
                # blows up with climate data as datetime is nanosecond resolution and
                # span we want can't be stored
                # TODO: find issue that relates to this
                time = data["time"]
                data = data.rename({"time": "year"}, axis="columns")
                data["year"] = 1212
                super().__init__(data)
                self.data = self.data.drop("year", axis="columns")
                self.data["time"] = time.values
                self.time_col = "time"
        else:
            super().__init__(data)
