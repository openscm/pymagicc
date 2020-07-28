import re

import numpy as np
import pandas as pd

from pymagicc.definitions import (
    convert_magicc6_to_magicc7_variables,
    convert_magicc7_to_openscm_variables,
)
from pymagicc.errors import InvalidTemporalResError
from pymagicc.io.base import _Reader


class _BinData(object):
    def __init__(self, filepath):
        # read the entire file into memory
        with open(filepath, "rb") as fh:
            self.data = fh.read()
        self.data = memoryview(self.data)
        self.pos = 0

    def read_chunk(self, t):
        """
        Read out the next chunk of memory

        Values in fortran binary streams begin and end with the number of bytes
        :param t: Data type (same format as used by struct).
        :return: Numpy array if the variable is an array, otherwise a scalar.
        """
        size = self.data[self.pos : self.pos + 4].cast("i")[0]
        d = self.data[self.pos + 4 : self.pos + 4 + size]

        actual_size = self.data[self.pos + 4 + size : self.pos + 4 + size + 4].cast(
            "i"
        )[0]

        if not actual_size == size:
            raise AssertionError(
                "Expected data size: {}, got: {}".format(size, actual_size)
            )

        self.pos = self.pos + 4 + size + 4

        res = np.array(d.cast(t))

        # Return as a scalar or a numpy array if it is an array
        if res.size == 1:
            return res[0]
        return res


class _BinaryOutReader(_Reader):
    _regexp_capture_variable = re.compile(r"DAT\_(.*)\.BINOUT$")
    _default_todo_fill_value = "N/A"

    def read(self):
        # Read the entire file into memory
        data = _BinData(self.filepath)

        metadata = self.process_header(data)
        df, metadata, columns = self.process_data(data, metadata)

        return metadata, df, columns

    def process_header(self, data):
        """
        Reads the first part of the file to get some essential metadata

        # Returns
        return (dict): the metadata in the header
        """
        metadata = {
            "datacolumns": data.read_chunk("I"),
            "firstyear": data.read_chunk("I"),
            "lastyear": data.read_chunk("I"),
            "annualsteps": data.read_chunk("I"),
        }
        if metadata["annualsteps"] != 1:
            raise InvalidTemporalResError(
                "{}: Only annual files can currently be processed".format(self.filepath)
            )

        return metadata

    def process_data(self, stream, metadata):
        """
        Extract the tabulated data from the input file

        # Arguments
        stream (Streamlike object): A Streamlike object (nominally StringIO)
            containing the table to be extracted
        metadata (dict): metadata read in from the header and the namelist

        # Returns
        df (pandas.DataFrame): contains the data, processed to the standard
            MAGICCData format
        metadata (dict): updated metadata based on the processing performed
        """
        index = np.arange(metadata["firstyear"], metadata["lastyear"] + 1)

        # The first variable is the global values
        globe = stream.read_chunk("d")

        if not len(globe) == len(index):
            raise AssertionError(
                "Length of data doesn't match length of index: "
                "{} != {}".format(len(globe), len(index))
            )

        if metadata["datacolumns"] == 1:
            num_boxes = 0

            data = globe[:, np.newaxis]

            regions = ["World"]

        else:
            regions = stream.read_chunk("d")
            num_boxes = int(len(regions) / len(index))
            regions = regions.reshape((-1, num_boxes), order="F")

            data = np.concatenate((globe[:, np.newaxis], regions), axis=1)

            regions = [
                "World",
                "World|Northern Hemisphere|Ocean",
                "World|Northern Hemisphere|Land",
                "World|Southern Hemisphere|Ocean",
                "World|Southern Hemisphere|Land",
            ]

        df = pd.DataFrame(data, index=index)

        if isinstance(df.index, pd.core.indexes.numeric.Float64Index):
            df.index = df.index.to_series().round(3)

        df.index.name = "time"

        variable = convert_magicc6_to_magicc7_variables(
            self._get_variable_from_filepath()
        )
        variable = convert_magicc7_to_openscm_variables(variable)
        column_headers = {
            "variable": [variable] * (num_boxes + 1),
            "region": regions,
            "unit": ["unknown"] * len(regions),
            "todo": ["SET"] * len(regions),
        }

        return df, metadata, self._set_column_defaults(column_headers)
