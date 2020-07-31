import re

import numpy as np
import pandas as pd

from pymagicc.definitions import (
    convert_magicc6_to_magicc7_variables,
    convert_magicc7_to_openscm_variables,
    convert_magicc_to_openscm_regions,
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

    def reset(self):
        self.pos = 0


class _LegacyBinFormat:
    version = None

    @staticmethod
    def process_header(reader, stream):
        metadata = {
            "datacolumns": stream.read_chunk("I"),
            "firstyear": stream.read_chunk("I"),
            "lastyear": stream.read_chunk("I"),
            "annualsteps": stream.read_chunk("I"),
        }
        if metadata["annualsteps"] != 1:
            raise InvalidTemporalResError(
                "{}: Only annual files can currently be processed".format(
                    reader.filepath
                )
            )

        return metadata

    @staticmethod
    def process_data(reader, stream, metadata):
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
            reader._get_variable_from_filepath()
        )
        variable = convert_magicc7_to_openscm_variables(variable)
        column_headers = {
            "variable": [variable] * (num_boxes + 1),
            "region": regions,
            "unit": "unknown",
        }

        return df, metadata, column_headers


class _V2BinFormat(_LegacyBinFormat):
    version = 2

    @staticmethod
    def process_variable(stream):
        def _read_str(s):
            bytes = np.atleast_1d(s.read_chunk("c"))
            return b"".join(bytes.tolist()).decode()

        var_name = _read_str(stream)
        region = _read_str(stream)
        units = _read_str(stream)

        data = stream.read_chunk("d")

        return {"variable": var_name, "region": region, "unit": units}, data

    @classmethod
    def process_data(cls, reader, stream, metadata):
        index = np.arange(metadata["firstyear"], metadata["lastyear"] + 1)

        columns = {}
        data = []
        for i in range(metadata["datacolumns"]):
            column_header, column_data = cls.process_variable(stream)

            for k in column_header:
                if k not in columns:
                    columns[k] = []
                columns[k].append(column_header[k])
            data.append(column_data)

        df = pd.DataFrame(np.asarray(data).T, index=index)

        if isinstance(df.index, pd.core.indexes.numeric.Float64Index):
            df.index = df.index.to_series().round(3)

        df.index.name = "time"

        # Convert the regions to openscm regions
        columns["region"] = convert_magicc_to_openscm_regions(columns["region"])

        # Convert the variable names to openscm variables
        columns["variable"] = [
            d[4:] if d.startswith("DAT_") else d for d in columns["variable"]
        ]
        columns["variable"] = convert_magicc6_to_magicc7_variables(columns["variable"])
        columns["variable"] = convert_magicc7_to_openscm_variables(columns["variable"])

        return df, metadata, columns


def get_bin_format(version):
    bin_formats = [_LegacyBinFormat(), _V2BinFormat()]

    for f in bin_formats:
        if f.version == version:
            return f
    raise ValueError("No formatter for binary version: {}".format(version))


class _BinaryOutReader(_Reader):
    _regexp_capture_variable = re.compile(r"DAT\_(.*)\.BINOUT$")
    _default_todo_fill_value = "not_relevant"

    def _determine_bin_version(self, data):
        try:
            # Check the magicc magicc string
            key = data.read_chunk("c")
            if b"".join(key.tolist()) != b"magicc":
                data.reset()  # Legacy files don't have a magic block - reset to start of file
                return None
            return data.read_chunk("h")
        except TypeError:
            # Wrong data type?
            raise ValueError("{}: unexpected header format".format(self.filepath))

    def read(self):
        # Read the entire file into memory
        data = _BinData(self.filepath)

        file_version = self._determine_bin_version(data)
        self.format = get_bin_format(file_version)

        metadata = self.process_header(data)
        df, metadata, columns = self.process_data(data, metadata)

        return metadata, df, columns

    def process_header(self, data):
        return self.format.process_header(self, data)

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
        df, metadata, columns = self.format.process_data(self, stream, metadata)
        return df, metadata, self._set_column_defaults(columns)
