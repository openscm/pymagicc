import re
import warnings
from copy import deepcopy
from datetime import datetime
from numbers import Number
from os.path import basename, exists
from shutil import copyfileobj

import f90nml
import numpy as np
import pandas as pd
from f90nml.namelist import Namelist
from scmdata import ScmDataFrame
from six import StringIO

from .definitions import (
    DATA_HIERARCHY_SEPARATOR,
    DATTYPE_REGIONMODE_REGIONS,
    PART_OF_PRNFILE,
    PART_OF_SCENFILE_WITH_EMISSIONS_CODE_0,
    PART_OF_SCENFILE_WITH_EMISSIONS_CODE_1,
    convert_magicc6_to_magicc7_variables,
    convert_magicc7_to_openscm_variables,
    convert_magicc_to_openscm_regions,
    convert_pint_to_fortran_safe_units,
)
from .magicc_time import (
    _adjust_df_index_to_match_timeseries_type,
    convert_to_datetime,
    convert_to_decimal_year,
)
from .utils import apply_string_substitutions

DATTYPE_FLAG = "THISFILE_DATTYPE"
"""str: Flag used to indicate the file's data type in MAGICCC"""

REGIONMODE_FLAG = "THISFILE_REGIONMODE"
"""str: Flag used to indicate the file's region mode in MAGICCC"""

UNSUPPORTED_OUT_FILES = [
    r"CARBONCYCLE.*OUT",
    r"PF\_.*OUT",
    r"DATBASKET_.*",
    r".*INVERSE\_.*EMIS.*OUT",
    r".*INVERSEEMIS\.BINOUT",
    r"PRECIPINPUT.*OUT",
    r"TEMP_OCEANLAYERS.*\.BINOUT",
    r"TIMESERIESMIX.*OUT",
    r"SUMMARY_INDICATORS.OUT",
]
"""list: List of regular expressions which define output files we cannot read.

These files are nasty to read and not that useful hence are unsupported. The solution
for these files is to fix the output format rather than hacking the readers. Obviously
that doesn't help for the released MAGICC6 binary but there is nothing we can do
there. For MAGICC7, we should have a much nicer set.

Some more details about why these files are not supported:

- ``CARBONCYCLE.OUT`` has no units and we don't want to hardcode them
- Sub annual binary files (including volcanic RF) are asking for trouble
- Permafrost output files don't make any sense right now
- Output baskets have inconsistent variable names from other outputs
- Inverse emissions files (except `INVERSEEMIS.OUT`) have no units and we don't want
  to hardcode them
- We have no idea what the precipitation input is
- Temp ocean layers is hard to predict because it has many layers
- Time series mix output files don't have units or regions
- Summary indicator files are a brand new format for little gain
"""


def _unsupported_file(filepath):
    for outfile in UNSUPPORTED_OUT_FILES:
        if re.match(outfile, filepath):
            return True

    return False


class NoReaderWriterError(ValueError):
    """Exception raised when a valid Reader or Writer could not be found for the file"""

    pass


class InvalidTemporalResError(ValueError):
    """Exception raised when a file has a temporal resolution which cannot be processed"""

    pass


class _Reader(object):
    header_tags = [
        "compiled by",
        "contact",
        "data",
        "date",
        "description",
        "gas",
        "source",
        "unit",
        "magicc-version",
        "run",
        "run_id",
    ]
    _newline_char = "\n"
    _variable_line_keyword = "VARIABLE"
    _regexp_capture_variable = None
    _default_todo_fill_value = "SET"

    def __init__(self, filepath):
        self.filepath = filepath

    def read(self):
        nml_start, nml_end = self._set_lines_and_find_nml()

        metadata = self._derive_metadata(nml_start, nml_end)

        # Create a stream from the remaining lines, ignoring any blank lines
        stream = StringIO()
        cleaned_lines = [
            line.strip() for line in self.lines[nml_end + 1 :] if line.strip()
        ]
        stream.write("\n".join(cleaned_lines))
        stream.seek(0)

        df, metadata, column_headers = self.process_data(stream, metadata)

        return metadata, df, column_headers

    def _open_file(self):
        # TODO document this choice of encoding
        # We have to make a choice about special characters e.g. names with
        # umlauts. The standard seems to be utf-8 hence we set things up to
        # only work if the encoding is utf-8.
        return open(self.filepath, "r", encoding="utf-8", newline=self._newline_char)

    def _readlines(self, fh, metadata_only=False):
        if metadata_only:
            # read file line by line
            line = None
            while line != "":
                line = fh.readline()
                yield line

        else:
            # read whole file at once
            for line in fh.readlines():
                yield line

    def _set_lines_and_find_nml(self, metadata_only=False):
        """
        Set lines and find the start and end of the embedded namelist.

        Parameters
        ----------
        metadata_only : bool
            Should only the metadata be read? If yes, we will stop reading in lines
            as soon as we get to the end of the namelist.

        Returns
        -------
        (int, int)
            Start and end index for the namelist
        """
        nml_start = None
        nml_end = None
        with self._open_file() as f:
            lines = []

            for i, line in enumerate(self._readlines(f, metadata_only=metadata_only)):
                lines.append(line)

                if self._is_nml_start(line):
                    nml_start = i

                if (nml_start is not None) and self._is_nml_end(line):
                    nml_end = i
                    if metadata_only:
                        break

        self.lines = lines

        if (nml_start is None) or (nml_end is None):
            raise ValueError("Could not find namelist")

        return nml_start, nml_end

    @staticmethod
    def _is_nml_start(line):
        return line.strip().startswith("&THISFILE_SPECIFICATIONS")

    @staticmethod
    def _is_nml_end(line):
        return line.strip().startswith("/")

    def _derive_metadata(self, nml_start, nml_end):

        nml_values = self.process_metadata(self.lines[nml_start : nml_end + 1])

        # ignore all nml_values except units
        metadata = {
            key: value
            for key, value in nml_values.items()
            if key in ["units", "timeseriestype"]
        }
        header_metadata = self.process_header("".join(self.lines[:nml_start]))
        metadata.update(header_metadata)

        return metadata

    def process_metadata(self, lines):
        def preprocess_edge_cases(lines, inverse=False):
            replacements = {"W/m": "Wperm", "^": "superscript"}

            return apply_string_substitutions(lines, replacements, inverse=inverse)

        def postprocess_edge_cases(value):
            return preprocess_edge_cases(value, inverse=True)

        # TODO: replace with f90nml.reads when released (>1.0.2)
        parser = f90nml.Parser()

        lines = preprocess_edge_cases(lines)

        nml = parser._readstream(lines, {})

        metadata = {}
        for k in nml["THISFILE_SPECIFICATIONS"]:
            metadata_key = k.split("_")[1]
            try:
                # have to do this type coercion as nml reads things like
                # 10superscript22 J into a threepart list, [10,
                # 'superscript22', 'J'] where the first part is an int
                value = "".join([str(v) for v in nml["THISFILE_SPECIFICATIONS"][k]])
                metadata[metadata_key] = postprocess_edge_cases(value).strip()
            except TypeError:
                metadata[metadata_key] = nml["THISFILE_SPECIFICATIONS"][k]

        return metadata

    def process_data(self, stream, metadata):
        """
        Extract the tabulated data from the input file.

        Parameters
        ----------
        stream : Streamlike object
            A Streamlike object (nominally StringIO)
            containing the table to be extracted
        metadata : dict
            Metadata read in from the header and the namelist

        Returns
        -------
        (pandas.DataFrame, dict)
            The first element contains the data, processed to the standard
            MAGICCData format.
            The second element is th updated metadata based on the processing performed.
        """
        ch, metadata = self._get_column_headers_and_update_metadata(stream, metadata)
        df = self._convert_data_block_to_df(stream)

        if "timeseriestype" in metadata:
            df = _adjust_df_index_to_match_timeseries_type(
                df, metadata["timeseriestype"]
            )

        return df, metadata, ch

    def _convert_data_block_to_df(self, stream):
        """
        stream : Streamlike object
            A Streamlike object (nominally StringIO) containing the data to be
            extracted

        ch : dict
            Column headers to use for the output pd.DataFrame

        Returns
        -------
        :obj:`pd.DataFrame`
            Dataframe with processed datablock
        """
        df = pd.read_csv(
            stream,
            skip_blank_lines=True,
            delim_whitespace=True,
            header=None,
            index_col=0,
        )

        if isinstance(df.index, pd.core.indexes.numeric.Float64Index):
            df.index = df.index.to_series().round(3)

        # reset the columns to be 0..n instead of starting at 1
        df.columns = list(range(len(df.columns)))

        return df

    def _convert_to_string_columns(self, df):
        for categorical_column in [
            "variable",
            "todo",
            "unit",
            "region",
            "model",
            "scenario",
            "climate_model",
        ]:
            df[categorical_column] = df[categorical_column].astype(str)

        return df

    def _set_column_defaults(self, ch):
        length = len(ch["variable"])
        ch.setdefault("climate_model", ["unspecified"] * length)
        ch.setdefault("model", ["unspecified"] * length)
        ch.setdefault("scenario", ["unspecified"] * length)

        required_cols = [
            "variable",
            "todo",
            "unit",
            "region",
            "climate_model",
            "model",
            "scenario",
        ]
        for col in required_cols:
            if col not in ch:
                raise AssertionError("Missing column {}".format(col))

        return ch

    def _get_column_headers_and_update_metadata(self, stream, metadata):
        if self._magicc7_style_header():
            column_headers, metadata = self._read_magicc7_style_header(stream, metadata)

        else:
            column_headers, metadata = self._read_magicc6_style_header(stream, metadata)

        column_headers["variable"] = convert_magicc7_to_openscm_variables(
            column_headers["variable"]
        )
        column_headers["region"] = convert_magicc_to_openscm_regions(
            column_headers["region"]
        )

        return column_headers, metadata

    def _magicc7_style_header(self):
        return any(["TODO" in line for line in self.lines]) and any(
            ["UNITS" in line for line in self.lines]
        )

    def _read_magicc7_style_header(self, stream, metadata):
        # Note that regions header line is assumed to start with 'YEARS'
        # instead of 'REGIONS'
        column_headers = {
            "variable": self._read_data_header_line(
                stream, self._variable_line_keyword
            ),
            "todo": self._read_data_header_line(stream, "TODO"),
            "unit": self._read_data_header_line(stream, "UNITS"),
            "region": self._read_data_header_line(stream, "YEARS"),
        }
        metadata.pop("units", None)

        return column_headers, metadata

    def _read_magicc6_style_header(self, stream, metadata):
        # File written in MAGICC6 style with only one header line rest of
        # data must be inferred.
        # Note that regions header line is assumed to start with 'COLCODE'
        # or 'YEARS' instead of 'REGIONS'
        regions = self._read_data_header_line(stream, ["COLCODE", "YEARS"])

        try:
            unit = metadata["unit"]
            metadata.pop("unit")
        except KeyError:
            unit = metadata["units"]
            metadata.pop("units")

        if "(" in unit:
            regexp_capture_unit = re.compile(r".*\((.*)\)\s*$")
            unit = regexp_capture_unit.search(unit).group(1)

        variable = convert_magicc6_to_magicc7_variables(
            self._get_variable_from_filepath()
        )
        column_headers = {
            "variable": [variable] * len(regions),
            "todo": [self._default_todo_fill_value] * len(regions),
            "unit": [unit] * len(regions),
            "region": regions,
        }

        for k in ["unit", "units", "gas"]:
            try:
                metadata.pop(k)
            except KeyError:
                pass

        return column_headers, metadata

    def _get_variable_from_filepath(self):
        """
        Determine the file variable from the filepath.

        Returns
        -------
        str
            Best guess of variable name from the filepath
        """
        try:
            return self.regexp_capture_variable.search(self.filepath).group(1)
        except AttributeError:
            self._raise_cannot_determine_variable_from_filepath_error()

    @property
    def regexp_capture_variable(self):
        if self._regexp_capture_variable is None:
            raise NotImplementedError()
        return self._regexp_capture_variable

    def _raise_cannot_determine_variable_from_filepath_error(self):
        error_msg = "Cannot determine variable from filepath: {}".format(self.filepath)
        raise ValueError(error_msg)

    def process_header(self, header):
        """
        Parse the header for additional metadata.

        Parameters
        ----------
        header : str
            All the lines in the header.

        Returns
        -------
        dict
            The metadata in the header.
        """
        metadata = {}
        # assume we start in header in case we are looking at legacy file which
        # doesn't have the '---- HEADER ----' line
        in_header = True
        header_lines = []
        for line in header.split("\n"):
            line = line.strip()
            if not line:
                continue
            if line == "---- HEADER ----":
                in_header = True
            elif line == "---- METADATA ----":
                in_header = False
            else:
                if in_header:
                    for tag in self.header_tags:
                        tag_text = "{}:".format(tag)
                        if line.lower().startswith(tag_text):
                            metadata[tag] = line[len(tag_text) + 1 :].strip()
                            break
                    else:
                        header_lines.append(line)
                else:
                    if ":" not in line:
                        header_lines.append(line)
                    else:
                        bits = line.split(":")
                        key = bits[0]
                        value = ":".join(bits[1:])
                        metadata[key.strip()] = value.strip()

        if header_lines:
            metadata["header"] = "\n".join(header_lines)

        return metadata

    def _read_data_header_line(self, stream, expected_header):
        """Read a data header line, ensuring that it starts with the expected header

        Parameters
        ----------
        stream : :obj:`StreamIO`
            Stream object containing the text to read

        expected_header : str, list of strs
            Expected header of the data header line
        """
        pos = stream.tell()
        expected_header = (
            [expected_header] if isinstance(expected_header, str) else expected_header
        )
        for exp_hd in expected_header:
            tokens = stream.readline().split()
            try:
                if not tokens[0] == exp_hd:
                    raise AssertionError(
                        "Token '{}' does not match expected header "
                        "'{}'".format(tokens[0], exp_hd)
                    )

                return tokens[1:]

            except AssertionError:
                stream.seek(pos)
                continue

        assertion_msg = "Expected a header token of {}, got {}".format(
            expected_header, tokens[0]
        )
        raise AssertionError(assertion_msg)

    def _unify_magicc_regions(self, regions):
        region_mapping = {
            "GLOBAL": "GLOBAL",
            "NO": "NHOCEAN",
            "SO": "SHOCEAN",
            "NL": "NHLAND",
            "SL": "SHLAND",
            "NH-OCEAN": "NHOCEAN",
            "SH-OCEAN": "SHOCEAN",
            "NH-LAND": "NHLAND",
            "SH-LAND": "SHLAND",
        }
        return [region_mapping[r] for r in regions]

    def _read_units(self, column_headers):
        column_headers["unit"] = convert_pint_to_fortran_safe_units(
            column_headers["unit"], inverse=True
        )

        for i, unit in enumerate(column_headers["unit"]):
            if unit in ("W/m2", "W/m^2"):
                column_headers["unit"][i] = "W / m^2"

        return column_headers


class _FourBoxReader(_Reader):
    def _read_magicc6_style_header(self, stream, metadata):
        column_headers, metadata = super()._read_magicc6_style_header(stream, metadata)

        column_headers["region"] = self._unify_magicc_regions(column_headers["region"])

        if not len(set(column_headers["unit"])) == 1:
            raise AssertionError(
                "Only one unit should be found for a MAGICC6 style file"
            )

        return column_headers, metadata


class _ConcInReader(_FourBoxReader):
    _regexp_capture_variable = re.compile(r".*\_(\w*\-?\w*\_CONC)\.IN$")

    def _get_variable_from_filepath(self):
        variable = super()._get_variable_from_filepath()
        return convert_magicc6_to_magicc7_variables(variable)

    def _read_data_header_line(self, stream, expected_header):
        tokens = super()._read_data_header_line(stream, expected_header)
        return [t.replace("_MIXINGRATIO", "") for t in tokens]


class _OpticalThicknessInReader(_FourBoxReader):
    _regexp_capture_variable = re.compile(r".*\_(\w*\_OT)\.IN$")

    def _read_magicc6_style_header(self, stream, metadata):
        column_headers, metadata = super()._read_magicc6_style_header(stream, metadata)

        metadata["unit normalisation"] = column_headers["unit"][0]
        column_headers["unit"] = ["dimensionless"] * len(column_headers["unit"])

        return column_headers, metadata

    def _read_data_header_line(self, stream, expected_header):
        tokens = super()._read_data_header_line(stream, expected_header)
        return [t.replace("OT-", "") for t in tokens]


class _RadiativeForcingInReader(_FourBoxReader):
    _regexp_capture_variable = re.compile(r".*\_(\w*\_RF)\.(IN|MON)$")

    def _read_data_header_line(self, stream, expected_header):
        tokens = super()._read_data_header_line(stream, expected_header)
        return [t.replace("FORC-", "") for t in tokens]

    def _get_column_headers_and_update_metadata(self, stream, metadata):
        column_headers, metadata = super()._get_column_headers_and_update_metadata(
            stream, metadata
        )
        column_headers = self._read_units(column_headers)

        return column_headers, metadata


class _SurfaceTemperatureInReader(_FourBoxReader):
    _regexp_capture_variable = re.compile(r".*\_(SURFACE_TEMP)\.IN$")


class _EmisInReader(_Reader):
    def _read_units(self, column_headers):
        column_headers = super()._read_units(column_headers)

        units = column_headers["unit"]
        variables = column_headers["variable"]
        for i, (unit, variable) in enumerate(zip(units, variables)):
            unit = unit.replace("-", "")
            for tmass in ["Gt", "Mt", "kt", "t", "Pg", "Gg", "Mg", "kg", "g"]:
                if unit.startswith(tmass):
                    mass = tmass
                    break

            try:
                emissions_unit = unit.replace(mass, "")
            except NameError:
                raise ValueError("Unexpected emissions unit")

            if not emissions_unit or emissions_unit.replace(" ", "") == "/yr":
                emissions_unit = variable.split(DATA_HIERARCHY_SEPARATOR)[-1]
                if emissions_unit in ["MAGICC AFOLU", "MAGICC Fossil and Industrial"]:
                    emissions_unit = variable.split(DATA_HIERARCHY_SEPARATOR)[-2]

            if "/" not in emissions_unit:
                # TODO: think of a way to not have to assume years...
                emissions_unit = "{} / yr".format(emissions_unit)
            else:
                emissions_unit = re.sub(r"(\S)\s?/\s?yr", r"\1 / yr", emissions_unit)

            units[i] = "{} {}".format(mass.strip(), emissions_unit.strip())
            variables[i] = variable

        column_headers["unit"] = units
        column_headers["variable"] = variables

        return column_headers


class _StandardEmisInReader(_EmisInReader):
    _regexp_capture_variable = re.compile(r".*\_(\w*\_EMIS)\.IN$")
    _variable_line_keyword = "GAS"

    def _read_data_header_line(self, stream, expected_header):
        tokens = super()._read_data_header_line(stream, expected_header)
        return [t.replace("EMIS-", "") for t in tokens]

    def _get_column_headers_and_update_metadata(self, stream, metadata):
        column_headers, metadata = super()._get_column_headers_and_update_metadata(
            stream, metadata
        )

        tmp_vars = []
        for v in column_headers["variable"]:
            # TODO: work out a way to avoid this fragile check and calling the
            # conversion once in the superclass method and again below
            if v.endswith("_EMIS") or v.startswith("Emissions"):
                tmp_vars.append(v)
            else:
                tmp_vars.append(v + "_EMIS")

        column_headers["variable"] = convert_magicc7_to_openscm_variables(tmp_vars)
        column_headers = self._read_units(column_headers)

        return column_headers, metadata


class _HistEmisInReader(_StandardEmisInReader):
    pass


class _Scen7Reader(_StandardEmisInReader):
    _regexp_capture_variable = re.compile(r".*\_(\w*\-?\w*)\.SCEN7$")

    def _get_variable_from_filepath(self):
        """
        Determine the file variable from the filepath.

        Returns
        -------
        str
            Best guess of variable name from the filepath
        """
        return "{}_EMIS".format(super()._get_variable_from_filepath())


class _NonStandardEmisInReader(_EmisInReader):
    def _set_lines(self):
        with self._open_file() as f:
            self.lines = f.readlines()

    def read(self):
        self._set_lines()
        self._stream = self._get_stream()
        header_notes_lines = self._read_header()
        df, columns = self.read_data_block()
        header_notes_lines += self._read_notes()

        metadata = {"header": "".join(header_notes_lines)}
        metadata.update(self.process_header(metadata["header"]))

        return metadata, df, columns

    def _get_stream(self):
        # Create a stream to work with, ignoring any blank lines
        stream = StringIO()
        cleaned_lines = [line.strip() for line in self.lines if line.strip()]
        stream.write("\n".join(cleaned_lines))
        stream.seek(0)

        return stream

    def _read_header(self):
        raise NotImplementedError()

    def read_data_block(self):
        raise NotImplementedError()

    def _read_notes(self):
        raise NotImplementedError()


class _ScenReader(_NonStandardEmisInReader):
    def read(self):
        metadata, df, columns = super().read()
        columns["scenario"] = metadata.pop("scenario")

        return metadata, df, columns

    def _read_header(self):
        # I don't know how to do this without these nasty while True statements
        header_notes_lines = []
        end_of_notes_key = "WORLD"
        while True:
            prev_pos = self._stream.tell()
            line = self._stream.readline()
            if not line:
                raise ValueError(
                    "Reached end of file without finding {} which should "
                    "always be the first region in a SCEN file".format(end_of_notes_key)
                )

            if line.startswith(end_of_notes_key):
                self._stream.seek(prev_pos)
                break

            header_notes_lines.append(line)

        return header_notes_lines

    def process_header(self, header):
        """
        Parse the header for additional metadata.

        Parameters
        ----------
        header : str
            All the lines in the header.

        Returns
        -------
        dict
            The metadata in the header.
        """
        metadata = {"header": []}
        for i, line in enumerate(header.split("\n")):
            line = line.strip()
            if i < 2:
                continue  # top level keys, ignore
            if i == 2:
                metadata["scenario"] = line.replace("name: ", "")
            elif i == 3:
                metadata["description"] = line.replace("description: ", "")
            elif i == 4:
                metadata["notes"] = line.replace("notes: ", "")
            else:
                if line:
                    metadata["header"].append(line)

        metadata["header"] = "\n".join(metadata["header"])
        return metadata

    def read_data_block(self):
        number_years = int(self.lines[0].strip())

        # go through datablocks until there are none left
        while True:
            ch = {}
            pos_block = self._stream.tell()
            region = convert_magicc_to_openscm_regions(self._stream.readline().strip())

            try:
                variables = self._read_data_header_line(self._stream, ["YEARS", "YEAR"])
            except IndexError:  # tried to get variables from empty string
                break
            except AssertionError:  # tried to get variables from a notes line
                break

            variables = convert_magicc6_to_magicc7_variables(variables)
            ch["variable"] = convert_magicc7_to_openscm_variables(
                [v + "_EMIS" for v in variables]
            )

            ch["unit"] = self._read_data_header_line(self._stream, ["Yrs", "YEARS"])

            ch = self._read_units(ch)
            ch["todo"] = ["SET"] * len(variables)
            ch["region"] = [region] * len(variables)

            region_block = StringIO()
            for i in range(number_years):
                region_block.write(self._stream.readline())
            region_block.seek(0)

            region_df = self._convert_data_block_to_df(region_block)

            try:
                df = pd.concat([region_df, df], axis="columns")
                columns = {key: ch[key] + columns[key] for key in columns}
            except NameError:
                df = region_df
                columns = ch

        self._stream.seek(pos_block)

        try:
            return df, columns
        except NameError:
            error_msg = (
                "This is unexpected, please raise an issue on "
                "https://github.com/openscm/pymagicc/issues"
            )
            raise Exception(error_msg)

    def _read_notes(self):
        notes = []
        while True:
            line = self._stream.readline()
            if not line:
                break
            notes.append(line)

        return notes


class _RCPDatReader(_Reader):
    def read(self):
        nml_start, nml_end = self._set_lines_and_find_nml()

        # ignore all nml_values as they are redundant
        header = "".join(self.lines[:nml_start])
        metadata = self.process_header(header)

        # Create a stream from the remaining lines, ignoring any blank lines
        stream = StringIO()
        cleaned_lines = [
            line.strip() for line in self.lines[nml_end + 1 :] if line.strip()
        ]
        stream.write("\n".join(cleaned_lines))
        stream.seek(0)

        df, metadata, columns = self.process_data(stream, metadata)

        return metadata, df, columns

    def process_header(self, header):
        """
        Parse the header for additional metadata.

        Parameters
        ----------
        header : str
            All the lines in the header.

        Returns
        -------
        dict
            The metadata in the header.
        """
        metadata = {}

        lines_iterator = (line.strip() for line in header.split("\n"))
        for i in range(len(header.split("\n"))):
            line = next(lines_iterator)

            if not line:
                continue

            if line.strip().startswith("COLUMN_DESCRIPTION"):
                break
            if ":" not in line:
                continue
            split_vals = [v.strip() for v in line.split(":")]
            key = split_vals[0]

            if key.endswith("CONTACT"):
                # delete scenario from key as redundant
                key = "CONTACT"

            content = ":".join(split_vals[1:])
            if key == "NOTE":
                content = [content]
                line = next(lines_iterator)
                while line:
                    content.append(line)
                    line = next(lines_iterator)

            metadata[key.lower()] = content

        return metadata

    def process_data(self, stream, metadata):
        # check headers are as we expect
        self._read_data_header_line(stream, "COLUMN:")

        units = convert_pint_to_fortran_safe_units(
            self._read_data_header_line(stream, "UNITS:"), inverse=True
        )

        variables = self._convert_variables_to_openscm_variables(
            self._read_data_header_line(stream, "YEARS")
        )

        # no information in raw files hence have to hardcode
        regions = ["World"] * len(units)
        todos = ["SET"] * len(units)

        column_headers = {
            "unit": units,
            "variable": variables,
            "region": regions,
            "todo": todos,
        }
        column_headers = self._read_units(column_headers)
        if column_headers["variable"][0].startswith("Emissions"):
            # massive hack, refactor in cleanup
            converter = _EmisInReader("junk")
            # clean up ambiguous units so converter can do its thing
            column_headers["unit"] = [
                u.replace("kt/yr", "kt").replace("Mt/yr", "Mt")
                for u in column_headers["unit"]
            ]

            column_headers = converter._read_units(column_headers)

        column_headers["scenario"] = [metadata.pop("run")]
        column_headers["climate_model"] = [
            "MAGICC{}".format(metadata.pop("magicc-version"))
        ]

        df = self._convert_data_block_to_df(stream)

        return df, metadata, column_headers

    def _convert_variables_to_openscm_variables(self, rcp_variables):
        magicc7_vars = convert_magicc6_to_magicc7_variables(rcp_variables)
        # work out whether we have emissions, concentrations or radiative
        # forcing, I think this is the best way to do it given the stability
        # of the format
        first_var = magicc7_vars[0]
        if first_var == "CO2I":
            intermediate_vars = [m + "_EMIS" for m in magicc7_vars]
        elif first_var == "CO2EQ":
            intermediate_vars = [m + "_CONC" for m in magicc7_vars]
        elif first_var == "TOTAL_INCLVOLCANIC_RF":
            intermediate_vars = []
            for m in magicc7_vars:
                if not m.endswith("_RF"):
                    m = m + "_RF"
                intermediate_vars.append(m)
        elif first_var == "TOTAL_INCLVOLCANIC_ERF":
            intermediate_vars = []
            for m in magicc7_vars:
                if not m.endswith("_ERF"):
                    m = m + "_ERF"
                intermediate_vars.append(m)
        else:
            raise ValueError(
                "I don't know how you got this file, but the format is not recognised by pymagicc"
            )

        res = convert_magicc7_to_openscm_variables(intermediate_vars)

        return res


class _PrnReader(_NonStandardEmisInReader):
    def read(self):
        metadata, df, column_headers = super().read()

        # now fix labelling, have to copy index :(
        variables = convert_magicc6_to_magicc7_variables(column_headers["variable"])
        todos = ["SET"] * len(variables)
        region = convert_magicc_to_openscm_regions("WORLD")

        concs = False
        emms = False

        unit_keys = [k for k in metadata.keys() if k.lower() == "unit"]
        units = [metadata.pop(k) for k in unit_keys]
        if not units:
            # have to assume global emissions in tons
            emms = True
        elif len(units) != 1:
            error_msg = (
                "Cannot read {} as there are multiple units (prn files should "
                "contain only one unit)".format(self.filepath)
            )
            raise ValueError(error_msg)
        elif units[0] == "ppt":
            concs = True
        elif units[0] == "metric tons":
            emms = True

        if not (emms or concs):
            raise AssertionError("Should have detected either emms or concs...")

        if concs:
            unit = "ppt"
            variables = [v + "_CONC" for v in variables]
        elif emms:
            unit = "t"
            variables = [v + "_EMIS" for v in variables]

        column_headers = {
            "variable": convert_magicc7_to_openscm_variables(variables),
            "todo": todos,
            "unit": [unit] * len(variables),
            "region": [region] * len(variables),
        }
        if emms:
            column_headers = self._read_units(column_headers)

        for k in ["gas"]:
            try:
                metadata.pop(k)
            except KeyError:
                pass

        return metadata, df, self._set_column_defaults(column_headers)

    def _read_header(self):
        # ignore first line, not useful for read
        self._stream.readline()
        # I don't know how to do this without these nasty while True statements
        header_notes_lines = []
        end_of_notes_keys = ("CFC11", "CFC-11", "Years")
        while True:
            prev_pos = self._stream.tell()
            line = self._stream.readline()
            if not line:
                raise ValueError(
                    "Reached end of file without finding {} which should "
                    "always be the start of the data header line in a .prn file".format(
                        end_of_notes_keys
                    )
                )

            if line.startswith((end_of_notes_keys)):
                self._stream.seek(prev_pos)
                break

            header_notes_lines.append(line)

        return header_notes_lines

    def read_data_block(self):
        data_block_stream = StringIO()
        # read in data block header, removing "Years" because it's just confusing
        # and can't be used for validation as it only appears in some files.
        data_block_header_line = self._stream.readline().replace("Years", "").strip()
        variables = []
        col_width = 10

        for w in range(0, len(data_block_header_line), col_width):
            variable = data_block_header_line[w : w + col_width].strip()
            variables.append(variable)

        # update in read method using metadata
        todos = ["unknown"] * len(variables)
        units = ["unknown"] * len(variables)
        regions = ["unknown"] * len(variables)

        while True:
            prev_pos = self._stream.tell()
            line = self._stream.readline()
            if not line:
                # reached end of file
                break
            if not re.match(r"^\d{4}\s", line):
                break
            data_block_stream.write(line)

        yr_col_width = 4
        col_widths = [yr_col_width] + [10] * len(variables)
        data_block_stream.seek(0)
        df = pd.read_fwf(data_block_stream, widths=col_widths, header=None, index_col=0)
        df.index.name = "time"
        columns = {
            "variable": variables,
            "todo": todos,
            "unit": units,
            "region": regions,
        }

        # put stream back for notes reading
        self._stream.seek(prev_pos)

        return df, columns

    def _read_notes(self):
        notes = []
        while True:
            line = self._stream.readline()
            if not line:
                break
            notes.append(line)

        return notes


class _OutReader(_FourBoxReader):
    _regexp_capture_variable = re.compile(r"DAT\_(\w*)\.OUT$")
    _default_todo_fill_value = "N/A"

    def _get_column_headers_and_update_metadata(self, stream, metadata):
        column_headers, metadata = super()._get_column_headers_and_update_metadata(
            stream, metadata
        )
        column_headers = self._read_units(column_headers)

        return column_headers, metadata


class _EmisOutReader(_EmisInReader, _OutReader):
    pass


class _InverseEmisReader(_EmisOutReader):
    _regexp_capture_variable = re.compile(r"(INVERSEEMIS)\.OUT$")

    def _get_column_headers_and_update_metadata(self, stream, metadata):
        units = self._read_data_header_line(stream, "UNITS:")
        variables = convert_magicc7_to_openscm_variables(
            convert_magicc6_to_magicc7_variables(
                self._read_data_header_line(stream, "YEARS:")
            )
        )

        column_headers = {
            "variable": variables,
            "todo": [self._default_todo_fill_value] * len(variables),
            "unit": units,
            "region": ["World"] * len(variables),
        }

        for k in ["unit", "units", "gas"]:
            try:
                metadata.pop(k)
            except KeyError:
                pass

        # get rid of confusing units before passing to read_units
        column_headers["unit"] = [
            v.replace("kt/yr", "kt") for v in column_headers["unit"]
        ]
        column_headers = super()._read_units(column_headers)

        return column_headers, metadata


class _TempOceanLayersOutReader(_Reader):
    _regexp_capture_variable = re.compile(r"(TEMP\_OCEANLAYERS\_?\w*)\.OUT$")
    _default_todo_fill_value = "N/A"

    def _read_magicc6_style_header(self, stream, metadata):
        column_headers, metadata = super()._read_magicc6_style_header(stream, metadata)

        if set(column_headers["variable"]) == {"TEMP_OCEANLAYERS"}:
            region = "GLOBAL"
        elif set(column_headers["variable"]) == {"TEMP_OCEANLAYERS_NH"}:
            region = "NHOCEAN"
        elif set(column_headers["variable"]) == {"TEMP_OCEANLAYERS_SH"}:
            region = "SHOCEAN"
        else:
            self._raise_cannot_determine_variable_from_filepath_error()

        column_headers["variable"] = [
            "OCEAN_TEMP_" + line for line in column_headers["region"]
        ]
        column_headers["region"] = [region] * len(column_headers["region"])

        return column_headers, metadata


class _MAGReader(_Reader):
    def _get_column_headers_and_update_metadata(self, stream, metadata):
        column_headers, metadata = super()._get_column_headers_and_update_metadata(
            stream, metadata
        )
        column_headers = self._read_units(column_headers)

        return column_headers, metadata


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


def get_dattype_regionmode(regions, scen7=False):
    """
    Get the THISFILE_DATTYPE and THISFILE_REGIONMODE flags for a given region set.

    In all MAGICC input files, there are two flags: THISFILE_DATTYPE and
    THISFILE_REGIONMODE. These tell MAGICC how to read in a given input file. This
    function maps the regions which are in a given file to the value of these flags
    expected by MAGICC.

    Parameters
    ----------
    regions : list_like
        The regions to get THISFILE_DATTYPE and THISFILE_REGIONMODE flags for.

    scen7 : bool, optional
        Whether the file we are getting the flags for is a SCEN7 file or not.

    Returns
    -------
    dict
        Dictionary where the flags are the keys and the values are the value they
        should be set to for the given inputs.
    """
    region_dattype_row = _get_dattype_regionmode_regions_row(regions, scen7=scen7)

    dattype = DATTYPE_REGIONMODE_REGIONS[DATTYPE_FLAG.lower()][region_dattype_row].iloc[
        0
    ]
    regionmode = DATTYPE_REGIONMODE_REGIONS[REGIONMODE_FLAG.lower()][
        region_dattype_row
    ].iloc[0]

    return {DATTYPE_FLAG: dattype, REGIONMODE_FLAG: regionmode}


def get_region_order(regions, scen7=False):
    """
    Get the region order expected by MAGICC.

    Parameters
    ----------
    regions : list_like
        The regions to get THISFILE_DATTYPE and THISFILE_REGIONMODE flags for.

    scen7 : bool, optional
        Whether the file we are getting the flags for is a SCEN7 file or not.

    Returns
    -------
    list
        Region order expected by MAGICC for the given region set.
    """
    region_dattype_row = _get_dattype_regionmode_regions_row(regions, scen7=scen7)
    region_order = DATTYPE_REGIONMODE_REGIONS["regions"][region_dattype_row].iloc[0]

    return region_order


def _get_dattype_regionmode_regions_row(regions, scen7=False):
    regions_unique = set(
        [convert_magicc_to_openscm_regions(r, inverse=True) for r in set(regions)]
    )

    def find_region(x):
        return set(x) == regions_unique

    region_rows = DATTYPE_REGIONMODE_REGIONS["regions"].apply(find_region)

    scen7_rows = DATTYPE_REGIONMODE_REGIONS["thisfile_dattype"] == "SCEN7"
    dattype_rows = scen7_rows if scen7 else ~scen7_rows

    region_dattype_row = region_rows & dattype_rows
    if sum(region_dattype_row) != 1:
        error_msg = (
            "Unrecognised regions, they must be part of "
            "pymagicc.definitions.DATTYPE_REGIONMODE_REGIONS. If that doesn't make "
            "sense, please raise an issue at "
            "https://github.com/openscm/pymagicc/issues"
        )
        raise ValueError(error_msg)

    return region_dattype_row


class _CompactOutReader(_Reader):
    def read(self):
        compact_table = self._read_compact_table()

        return self._convert_compact_table_to_df_metadata_column_headers(compact_table)

    def _read_compact_table(self):
        with open(self.filepath, "r") as fh:
            headers = self._read_header(fh)
            # TODO: change to reading a limited number of lines
            lines_as_dicts = [line for line in self._read_lines(fh, headers)]

        return pd.DataFrame(lines_as_dicts)

    def _read_header(self, fh):
        line = fh.readline().strip(",\n")
        return [item.strip('"') for item in line.split(",")]

    def _read_lines(self, fh, headers):
        for line in fh:
            toks = line.strip(",\n").split(",")

            if not len(toks) == len(headers):
                raise AssertionError("# headers does not match # lines")

            yield {h: float(v) for h, v in zip(headers, toks)}

    def _convert_compact_table_to_df_metadata_column_headers(self, compact_table):
        ts_cols = [c for c in compact_table if "__" in c]
        para_cols = [c for c in compact_table if "__" not in c]

        ts = compact_table[ts_cols]
        ts = ts.T

        def sort_ts_ids(inid):
            variable, region, year = inid.split("__")
            variable = variable.replace("DAT_", "")

            return {"variable": variable, "region": region, "year": year}

        ts["variable"] = ts.index.map(
            lambda x: convert_magicc7_to_openscm_variables(
                x.split("__")[0].replace("DAT_", "")
            )
        )
        ts["region"] = ts.index.map(
            lambda x: convert_magicc_to_openscm_regions(x.split("__")[1])
        )

        ts["year"] = ts.index.map(lambda x: x.split("__")[2])
        # Make sure all the year strings are four characters long. Not the best test,
        # but as good as we can do for now.
        if not (ts["year"].apply(len) == 4).all():  # pragma: no cover # safety valve
            raise NotImplementedError("Non-annual data not yet supported")

        ts["year"] = ts["year"].astype(int)

        ts = ts.reset_index(drop=True)

        id_cols = {"variable", "region", "year"}
        run_cols = set(ts.columns) - id_cols
        ts = ts.melt(value_vars=run_cols, var_name="run_id", id_vars=id_cols)

        ts["unit"] = "unknown"

        new_index = list(set(ts.columns) - {"value"})
        ts = ts.set_index(new_index)["value"].unstack("year")

        paras = compact_table[para_cols]
        paras.index.name = "run_id"

        cols_to_merge = find_parameter_groups(paras.columns.tolist())

        paras_clean = paras.copy()
        # Aggregate the columns
        for new_col, components in cols_to_merge.items():
            components = sorted(components)
            paras_clean.loc[:, new_col] = tuple(paras[components].values.tolist())
            paras_clean = paras_clean.drop(columns=components)

        years = ts.columns.tolist()
        ts = ts.reset_index().set_index("run_id")
        out = pd.merge(ts, paras_clean, left_index=True, right_index=True).reset_index()

        id_cols = set(out.columns) - set(years)
        out = out.melt(value_vars=years, var_name="year", id_vars=id_cols)
        new_index = list(set(out.columns) - {"value"})
        out = out.set_index(new_index)["value"].unstack("year")
        out = out.T

        column_headers = {
            name.lower(): out.columns.get_level_values(name).tolist()
            for name in out.columns.names
        }
        df = out.copy()
        metadata = {}

        return metadata, df, column_headers


class _BinaryCompactOutReader(_CompactOutReader):
    def _read_compact_table(self):
        with open(self.filepath, "rb") as fh:
            headers = self._read_header(fh)
            # can change to reading limited number of lines in future
            lines_as_dicts = [line for line in self._read_lines(fh, headers)]

        return pd.DataFrame(lines_as_dicts)

    def _read_header(self, fh):
        first_value = self._read_item(fh).tobytes()
        if not first_value == b"COMPACT_V1":
            raise AssertionError("Unexpected first value: {}".format(first_value))

        second_value = self._read_item(fh).tobytes()
        if not second_value == b"HEAD":
            raise AssertionError("Unexpected second value: {}".format(second_value))

        items = []
        while True:
            item = self._read_item(fh)
            if item is None or item.tobytes() == b"END":
                break
            items.append(item.tobytes().decode())

        return items

    def _read_lines(self, fh, headers):
        while True:

            items = self._read_item(fh)
            if items is None:
                break

            # Read the values as an array of floats (4 byte)
            items = items.cast("f")
            if len(items) != len(headers):
                raise AssertionError("# headers does not match # lines")

            # Check the line terminator
            item = self._read_item(fh)
            if not item.tobytes() == b"END":
                raise AssertionError(
                    "Unexpected final line value: {}".format(item.tobytes())
                )

            yield {h: float(v) for h, v in zip(headers, items.tolist())}

    def _read_item(self, fh):
        # Fortran writes out a 4 byte integer representing the # of bytes to read for
        # a given chunk, the data and then the size again
        d = fh.read(4)
        if d != b"":
            s = memoryview(d).cast("i")[0]
            item = memoryview(fh.read(s))
            s_after = memoryview(fh.read(4)).cast("i")[0]
            if not s_after == s:
                raise AssertionError(
                    "Wrong size after data. Before: {}. " "After: {}".format(s, s_after)
                )

            return item


class _Writer(object):
    """Base class for writing MAGICC input files.

    Attributes
    ----------
    _magicc_version : int
        The MAGICC version for which we want to write files. MAGICC7 and MAGICC6
        namelists are incompatible hence we need to know which one we're writing for.

    _scen_7 : bool
        Whether this writer writes SCEN7 files or not. We need this as SCEN7 files
        have a unique definition of what the THISFILE_REGIONMODE flag should be set to
        which is contradictory to all other files.
    """

    _magicc_version = 7
    _scen_7 = False
    _newline_char = "\n"
    _variable_header_row_name = "VARIABLE"

    def __init__(self, magicc_version=7):
        self._magicc_version = magicc_version

    def write(self, magicc_input, filepath):
        """
        Write a MAGICC input file from df and metadata

        Parameters
        ----------
        magicc_input : :obj:`pymagicc.io.MAGICCData`
            MAGICCData object which holds the data to write

        filepath : str
            Filepath of the file to write to.
        """
        self._filepath = filepath
        # TODO: make copy attribute for MAGICCData
        self.minput = deepcopy(magicc_input)
        self.data_block = self._get_data_block()

        output = StringIO()

        output = self._write_header(output)
        # TODO: fix this logic. The datablock and the namelist are tightly coupled so
        # they should be written together too. At the moment the datablock is
        # generated twice which is not fast (I suspect, haven't actually checked).
        output = self._write_namelist(output)
        output = self._write_datablock(output)

        with open(
            filepath, "w", encoding="utf-8", newline=self._newline_char
        ) as output_file:
            output.seek(0)
            copyfileobj(output, output_file)

    def _write_header(self, output):
        output.write(self._get_header())
        return output

    def _get_header(self):
        try:
            header = self.minput.metadata.pop("header")
        except KeyError:
            raise KeyError(
                'Please provide a file header in ``self.metadata["header"]``'
            )

        md = self.minput.metadata
        sorted_keys = sorted(md.keys())
        metadata = "\n".join(["{}: {}".format(k, md[k]) for k in sorted_keys])

        return (
            "---- HEADER ----\n"
            "\n"
            "{}\n"
            "\n"
            "---- METADATA ----\n"
            "\n"
            "{}\n"
            "\n".format(header, metadata)
        )

    def _write_namelist(self, output):
        nml_initial, data_block = self._get_initial_nml_and_data_block()
        nml = nml_initial.copy()

        # '&NML_INDICATOR' goes above, '/'' goes at end
        number_lines_nml_header_end = 2
        line_after_nml = self._newline_char

        try:
            number_col_headers = len(data_block.columns.levels)
        except AttributeError:
            if not isinstance(data_block.columns, pd.core.indexes.base.Index):
                raise AssertionError(
                    "Unexpected type of `data_block.columns`: "
                    "{}".format(type(data_block.columns))
                )

            number_col_headers = 1

        if self._magicc_version == 6:
            nml["THISFILE_SPECIFICATIONS"].pop("THISFILE_REGIONMODE")
            nml["THISFILE_SPECIFICATIONS"].pop("THISFILE_DATAROWS")

        nml["THISFILE_SPECIFICATIONS"]["THISFILE_FIRSTDATAROW"] = (
            len(output.getvalue().split(self._newline_char))
            + len(nml["THISFILE_SPECIFICATIONS"])
            + number_lines_nml_header_end
            + len(line_after_nml.split(self._newline_char))
            + number_col_headers
        )

        nml.uppercase = True
        nml._writestream(output)
        output.write(line_after_nml)

        return output

    def _write_datablock(self, output):
        _, data_block = self._get_initial_nml_and_data_block()

        # for most data files, as long as the data is space separated, the
        # format doesn't matter
        time_col_length = 11
        time_col = data_block.iloc[:, 0]
        if (time_col == time_col.astype(int)).all():
            time_col_format = "d"
        else:
            time_col_format = "f"

        first_col_format_str = (
            "{" + ":{}{}".format(time_col_length, time_col_format) + "}"
        ).format
        other_col_format_str = "{:19.5e}".format
        formatters = [other_col_format_str] * len(data_block.columns)
        formatters[0] = first_col_format_str

        data_block.to_string(output, index=False, formatters=formatters, sparsify=False)

        output.write(self._newline_char)
        return output

    def _get_initial_nml_and_data_block(self):
        data_block = self.data_block

        regions = convert_magicc_to_openscm_regions(
            data_block.columns.get_level_values("region").tolist(), inverse=True
        )
        regions = self._ensure_file_region_type_consistency(regions)
        variables = convert_magicc7_to_openscm_variables(
            data_block.columns.get_level_values("variable").tolist(), inverse=True
        )
        # trailing EMIS is incompatible, for now
        variables = [v.replace("_EMIS", "") for v in variables]
        units = convert_pint_to_fortran_safe_units(
            data_block.columns.get_level_values("unit").tolist()
        )
        todos = data_block.columns.get_level_values("todo").tolist()

        data_block = data_block.rename(columns=str).reset_index()
        data_block.columns = [
            [self._variable_header_row_name] + variables,
            ["TODO"] + todos,
            ["UNITS"] + units,
            ["YEARS"] + regions,
        ]

        nml = Namelist()
        nml["THISFILE_SPECIFICATIONS"] = Namelist()
        nml["THISFILE_SPECIFICATIONS"]["THISFILE_DATACOLUMNS"] = (
            len(data_block.columns) - 1  # for YEARS column
        )
        nml["THISFILE_SPECIFICATIONS"]["THISFILE_DATAROWS"] = len(data_block)
        nml["THISFILE_SPECIFICATIONS"]["THISFILE_FIRSTYEAR"] = int(
            np.floor(data_block.iloc[0, 0])
        )
        nml["THISFILE_SPECIFICATIONS"]["THISFILE_LASTYEAR"] = int(
            np.floor(data_block.iloc[-1, 0])
        )

        step_length = data_block.iloc[1:, 0].values - data_block.iloc[:-1, 0].values
        try:
            np.testing.assert_allclose(step_length, step_length[0], rtol=0.02)
            step_length = step_length[0]
            annual_steps = np.round(1 / step_length, 1)
            if annual_steps < 1:
                annual_steps = 0
            else:
                annual_steps = int(annual_steps)
        except AssertionError:
            annual_steps = 0  # irregular timesteps
        nml["THISFILE_SPECIFICATIONS"]["THISFILE_ANNUALSTEPS"] = annual_steps

        units_unique = list(set(self._get_df_header_row("unit")))
        nml["THISFILE_SPECIFICATIONS"]["THISFILE_UNITS"] = (
            convert_pint_to_fortran_safe_units(units_unique[0])
            if len(units_unique) == 1
            else "MISC"
        )

        nml["THISFILE_SPECIFICATIONS"].update(self._get_dattype_regionmode(regions))

        return nml, data_block

    def _get_dattype_regionmode(self, regions):
        return get_dattype_regionmode(regions, scen7=self._scen_7)

    def _ensure_file_region_type_consistency(self, regions):
        # no checks required except for certain cases
        return regions

    def _get_data_block(self):
        data_block = self.minput.timeseries(
            meta=["variable", "todo", "unit", "region"]
        ).T
        self._check_data_block_column_names(data_block)
        self._check_data_filename_variable_consistency(data_block)

        region_col = "region"
        other_names = [n for n in data_block.columns.names if n != region_col]

        # do transpose to guarantee row ordering (see
        # https://stackoverflow.com/a/40950331), not the case for column ordering
        # annoyingly...
        data_block_grouper = data_block.T.groupby(level=other_names, sort=False)

        def order_regions(df):
            region_order_df = df.T
            region_order = self._get_region_order(region_order_df)
            reordered = df.reindex(region_order, level=region_col)
            reordered.index = reordered.index.get_level_values(region_col)

            return reordered

        data_block = data_block_grouper.apply(order_regions).T

        data_block = self._convert_data_block_to_magicc_time(data_block)

        return data_block

    @staticmethod
    def _check_data_block_column_names(data_block):
        # probably not necessary but a sensible check
        if not data_block.columns.names == ["variable", "todo", "unit", "region"]:
            raise AssertionError(
                "Unexpected data block columns: " "{}".format(data_block.columns.names)
            )

    def _get_region_order(self, data_block):
        regions = data_block.columns.get_level_values("region").tolist()
        region_order_magicc = get_region_order(regions, self._scen_7)

        region_order = convert_magicc_to_openscm_regions(region_order_magicc)
        unrecognised_regions = set(regions) - set(region_order)
        if unrecognised_regions:
            error_msg = (
                "Are all of your regions OpenSCM regions? I don't "
                "recognise: {}".format(sorted(unrecognised_regions))
            )
            raise ValueError(error_msg)

        return region_order

    def _check_data_filename_variable_consistency(self, data_block):
        data_var = data_block.columns.get_level_values("variable").unique()
        if len(data_var) == 1:
            data_var = data_var[0]
            filename_var = _get_openscm_var_from_filepath(self._filepath)
            if data_var != filename_var:
                error_msg = (
                    "Your filename variable, {}, does not match the data "
                    "variable, {}".format(filename_var, data_var)
                )
                raise ValueError(error_msg)

    def _convert_data_block_to_magicc_time(self, data_block):
        timestamp_months = data_block.index.map(lambda x: x.month)
        number_months = len(timestamp_months.unique())
        if number_months == 1:  # yearly data
            data_block.index = data_block.index.map(lambda x: x.year)
        else:
            data_block.index = data_block.index.map(convert_to_decimal_year)

        return data_block

    def _get_df_header_row(self, col_name):
        return self.data_block.columns.get_level_values(col_name).tolist()


class _ConcInWriter(_Writer):
    pass


class _OpticalThicknessInWriter(_Writer):
    pass


class _RadiativeForcingInWriter(_Writer):
    pass


class _SurfaceTemperatureInWriter(_Writer):
    pass


class _HistEmisInWriter(_Writer):
    _variable_header_row_name = "GAS"

    def _get_df_header_row(self, col_name):
        hr = super()._get_df_header_row(col_name)
        return [v.replace("_EMIS", "") for v in hr]


class _Scen7Writer(_HistEmisInWriter):
    _scen_7 = True

    def _ensure_file_region_type_consistency(self, regions):
        rcp_regions_mapping = {
            r: r.replace("R5", "R5.2")
            for r in ["R5ASIA", "R5LAM", "R5REF", "R5MAF", "R5OECD"]
        }

        if not any([r in regions for r in rcp_regions_mapping]):
            return regions

        new_regions = [
            rcp_regions_mapping[r] if r in rcp_regions_mapping else r for r in regions
        ]
        warn_msg = (
            "MAGICC6 RCP region naming (R5*) is not compatible with "
            "MAGICC7, automatically renaming to MAGICC7 compatible regions "
            "(R5.2*)"
        )
        warnings.warn(warn_msg)

        return new_regions


class _PrnWriter(_Writer):
    def _write_header(self, output):
        unit = self._get_unit()

        if unit == "t":
            unit = "metric tons"
        self.minput.metadata["unit"] = unit
        output.write(self._get_header())
        return output

    def _write_namelist(self, output):
        return output

    def _write_datablock(self, output):
        lines = output.getvalue().split(self._newline_char)

        unit = self._get_unit()
        if unit == "t":
            other_col_format_str = "{:9.0f}".format
        elif unit == "ppt":
            other_col_format_str = "{:9.3e}".format

        data_block = self._get_data_block()

        # line with number of rows to skip, start year and end year
        number_indicator_lines = 1
        number_blank_lines_after_indicator = 1

        number_header_lines = len(lines)
        number_blank_lines_after_header = 1

        data_block_header_rows = 1
        number_blank_lines_after_data_block_header_rows = 1

        # we don't need other blank lines as they're skipped in source anyway
        line_above_data_block = (
            number_indicator_lines
            + number_blank_lines_after_indicator
            + number_header_lines
            + number_blank_lines_after_header
            + data_block_header_rows
            + number_blank_lines_after_data_block_header_rows
        )

        firstyear = int(np.floor(data_block.iloc[0, 0]))
        lastyear = int(np.floor(data_block.iloc[-1, 0]))
        indicator_line = "{:10d}{:10d}{:10d}".format(
            line_above_data_block, firstyear, lastyear
        )
        lines.insert(0, indicator_line)
        lines.insert(1, "")
        lines.append("")

        # format is irrelevant for the source
        # however it does matter for reading in again with pymagicc
        time_col_length = 10
        first_col_format_str = ("{" + ":{}d".format(time_col_length) + "}").format

        formatters = [other_col_format_str] * len(data_block.columns)
        formatters[0] = first_col_format_str

        col_headers = data_block.columns.tolist()
        col_header = (
            " {: <10}".format(col_headers[0])
            + "".join(["{: <10}".format(c) for c in col_headers[1:]]).strip()
        )
        lines.append(col_header)
        lines.append("")  # add blank line between data block header and data block

        data_block_str = data_block.to_string(
            index=False, header=False, formatters=formatters, sparsify=False
        )

        lines.append(data_block_str)
        lines.append("")  # new line at end of file
        output.seek(0)
        output.write(self._newline_char.join(lines))

        return output

    def _get_unit(self):
        units = self.minput["unit"].unique().tolist()

        unit = units[0].split(" ")[0]
        if unit == "t":
            if not all([u.startswith("t ") and u.endswith(" / yr") for u in units]):
                raise AssertionError(
                    "Prn emissions file with units other than tonne per year won't work"
                )

        elif unit == "ppt":
            if not all([u == "ppt" for u in units]):
                raise AssertionError(
                    "Prn concentrations file with units other than ppt won't work"
                )

        else:
            error_msg = (
                "prn file units should either all be 'ppt' or all be 't [gas] / yr', "
                "units of {} do not meet this requirement".format(units)
            )
            raise ValueError(error_msg)

        return unit

    def _get_data_block(self):
        data_block = self.minput.timeseries(
            meta=["variable", "todo", "unit", "region"]
        ).T
        self._check_data_block_column_names(data_block)

        regions = data_block.columns.get_level_values("region").unique()
        region_error_msg = ".prn files can only contain the 'World' region"
        if not (len(regions) == 1) and (regions[0] == "World"):
            raise AssertionError(region_error_msg)

        magicc7_vars = convert_magicc7_to_openscm_variables(
            data_block.columns.get_level_values("variable"), inverse=True
        )

        old_style_vars = [
            v.replace("_EMIS", "").replace("_CONC", "") for v in magicc7_vars
        ]
        data_block.columns = old_style_vars

        emms_assert_msg = (
            "Prn files must have, and only have, "
            "the following species: {}".format(PART_OF_PRNFILE)
        )
        if not (set(data_block.columns) == set(PART_OF_PRNFILE)):
            raise AssertionError(emms_assert_msg)

        data_block = data_block[PART_OF_PRNFILE]

        data_block.index.name = "Years"
        data_block = self._convert_data_block_to_magicc_time(data_block)
        data_block.reset_index(inplace=True)

        return data_block


class _ScenWriter(_Writer):
    SCEN_VARS_CODE_0 = convert_magicc7_to_openscm_variables(
        [v + "_EMIS" for v in PART_OF_SCENFILE_WITH_EMISSIONS_CODE_0]
    )
    SCEN_VARS_CODE_1 = convert_magicc7_to_openscm_variables(
        [v + "_EMIS" for v in PART_OF_SCENFILE_WITH_EMISSIONS_CODE_1]
    )

    def write(self, magicc_input, filepath):
        orig_length = len(magicc_input)
        orig_vars = magicc_input["variable"]

        if not (set(self.SCEN_VARS_CODE_1) - set(orig_vars)):
            magicc_input.filter(variable=self.SCEN_VARS_CODE_1, inplace=True)
        elif not (set(self.SCEN_VARS_CODE_0) - set(orig_vars)):
            magicc_input.filter(variable=self.SCEN_VARS_CODE_0, inplace=True)
        if len(magicc_input) != orig_length:
            warnings.warn("Ignoring input data which is not required for .SCEN file")

        super().write(magicc_input, filepath)

    def _write_header(self, output):
        header_lines = []
        header_lines.append("{}".format(len(self.data_block)))

        variables = self._get_df_header_row("variable")
        variables = convert_magicc7_to_openscm_variables(variables, inverse=True)
        variables = [v.replace("_EMIS", "") for v in variables]

        regions = self._get_df_header_row("region")
        regions = convert_magicc_to_openscm_regions(regions, inverse=True)
        regions = self._ensure_file_region_type_consistency(regions)

        special_scen_code = get_special_scen_code(regions=regions, emissions=variables)

        header_lines.append("{}".format(special_scen_code))

        # for a scen file, the convention is (although all these lines are
        # actually ignored by source so could be anything):
        # - line 3 is name
        # - line 4 is description
        # - line 5 is notes (other notes lines go at the end)
        # - line 6 is empty
        header_lines.append("name: {}".format(self.minput["scenario"].unique()[0]))
        header_lines.append(
            "description: {}".format(
                self.minput.metadata.pop(
                    "description", "metadata['description'] is written here"
                )
            )
        )
        header_lines.append(
            "notes: {}".format(
                self.minput.metadata.pop("notes", "metadata['notes'] is written here")
            )
        )
        header_lines.append("")

        try:
            header_lines.append(self.minput.metadata.pop("header"))
        except KeyError:
            pass
        for k, v in self.minput.metadata.items():
            header_lines.append("{}: {}".format(k, v))

        output.write(self._newline_char.join(header_lines))
        output.write(self._newline_char)

        return output

    def _write_namelist(self, output):
        # No namelist for SCEN files
        return output

    def _write_datablock(self, output):
        # for SCEN files, the data format is vitally important for the source code
        # we have to work out a better way of matching up all these conventions/testing them, tight coupling between pymagicc and MAGICC may solve it for us...
        lines = output.getvalue().split(self._newline_char)
        # notes are everything except the first 6 lines
        number_notes_lines = len(lines) - 6

        def _gip(lines, number_notes_lines):
            """
            Get the point where we should insert the data block.
            """
            return len(lines) - number_notes_lines

        region_order_db = get_region_order(
            self._get_df_header_row("region"), scen7=self._scen_7
        )
        region_order_magicc = self._ensure_file_region_type_consistency(region_order_db)
        # format is vitally important for SCEN files as far as I can tell
        time_col_length = 11
        first_col_format_str = ("{" + ":{}d".format(time_col_length) + "}").format
        other_col_format_str = "{:10.4f}".format

        # TODO: doing it this way, out of the loop,  should ensure things
        # explode if your regions don't all have the same number of emissions
        # timeseries or does extra timeseries in there (that probably
        # shouldn't raise an error, another one for the future), although the
        # explosion will be cryptic so should add a test for good error
        # message at some point
        formatters = [other_col_format_str] * (
            int(len(self.data_block.columns) / len(region_order_db))
            + 1  # for the years column
        )
        formatters[0] = first_col_format_str

        variables = convert_magicc7_to_openscm_variables(
            self._get_df_header_row("variable"), inverse=True
        )
        variables = [v.replace("_EMIS", "") for v in variables]

        special_scen_code = get_special_scen_code(
            regions=region_order_magicc, emissions=variables
        )
        if special_scen_code % 10 == 0:
            variable_order = PART_OF_SCENFILE_WITH_EMISSIONS_CODE_0
        else:
            variable_order = PART_OF_SCENFILE_WITH_EMISSIONS_CODE_1

        for region_db, region_magicc in zip(region_order_db, region_order_magicc):
            region_block_region = convert_magicc_to_openscm_regions(region_db)
            region_block = self.data_block.xs(
                region_block_region, axis=1, level="region", drop_level=False
            )
            region_block.columns = region_block.columns.droplevel("todo")
            region_block.columns = region_block.columns.droplevel("region")

            variables = region_block.columns.levels[0]
            variables = convert_magicc7_to_openscm_variables(variables, inverse=True)
            region_block.columns = region_block.columns.set_levels(
                levels=[v.replace("_EMIS", "") for v in variables], level="variable",
            )

            region_block = region_block.reindex(
                variable_order, axis=1, level="variable"
            )

            variables = region_block.columns.get_level_values("variable").tolist()
            variables = convert_magicc6_to_magicc7_variables(
                [v.replace("_EMIS", "") for v in variables], inverse=True
            )

            units = convert_pint_to_fortran_safe_units(
                region_block.columns.get_level_values("unit").tolist()
            )
            # column widths don't work with expressive units
            units = [u.replace("_", "").replace("peryr", "") for u in units]

            if not (region_block.columns.names == ["variable", "unit"]):
                raise AssertionError(
                    "Unexpected region block columns: "
                    "{}".format(region_block.columns.names)
                )

            region_block = region_block.rename(columns=str).reset_index()
            region_block.columns = [["YEARS"] + variables, ["Yrs"] + units]

            region_block_str = region_magicc + self._newline_char
            region_block_str += region_block.to_string(
                index=False, formatters=formatters, sparsify=False
            )
            region_block_str += self._newline_char * 2

            lines.insert(_gip(lines, number_notes_lines), region_block_str)

        output.seek(0)
        output.write(self._newline_char.join(lines))
        return output

    def _ensure_file_region_type_consistency(self, regions):
        magicc7_regions_mapping = {
            r: r.replace("R5.2", "R5")
            for r in ["R5.2ASIA", "R5.2LAM", "R5.2REF", "R5.2MAF", "R5.2OECD"]
        }

        if not any([r in regions for r in magicc7_regions_mapping]):
            return regions

        new_regions = [
            magicc7_regions_mapping[r] if r in magicc7_regions_mapping else r
            for r in regions
        ]
        warn_msg = (
            "MAGICC7 RCP region naming (R5.2*) is not compatible with "
            "MAGICC6, automatically renaming to MAGICC6 compatible regions "
            "(R5*)"
        )
        warnings.warn(warn_msg)

        return new_regions


class _RCPDatWriter(_Writer):
    def _get_header(self):
        """
        Get the header for an RCPData file

        This uses the deeply unsatisfactory, but only practical (at least until we
        have a proper hierarchy of variables in Pymagicc) solution of using default
        MAGICC categories and hard-coding descriptions (which can vary by MAGICC
        version).
        """
        warnings.warn(
            "The `.DAT` format is an old, custom format. We strongly recommend using "
            "the `ScmDataFrame` format instead (just call `.to_csv()`). Our `.DAT` "
            "writers are not super well tested so the error messages are likely "
            "to be cryptic. If you need help, please raise an issue at "
            "https://github.com/openscm/pymagicc/issues"
        )
        if self._filepath.endswith("_RADFORCING.DAT"):
            return self._get_header_radforcing()

        if self._filepath.endswith("_EFFECTIVERADFORCING.DAT"):
            if self._magicc_version == 6:
                raise ValueError("MAGICC6 does not output effective radiative forcing")

            return self._get_header_effradforcing()

        if self._filepath.endswith("_EMISSIONS.DAT"):
            return self._get_header_emissions()

        if self._filepath.endswith("_CONCENTRATIONS.DAT"):
            return self._get_header_concentrations()

        raise NotImplementedError

    def _get_header_radforcing(self):
        scenario = self.minput.get_unique_meta("scenario", no_duplicates=True)
        magicc_version = self.minput.get_unique_meta(
            "climate_model", no_duplicates=True
        )
        if magicc_version.startswith("MAGICC"):
            magicc_version = magicc_version.replace("MAGICC", "")
        else:
            raise AssertionError("climate_model should start with `MAGICC`")
        meta = self.minput.metadata
        extra_fgases = (
            ""
            if self._magicc_version == 6
            else " plus C3F8, C4F10, C5F12, C7F16, C8F18, CC4F8, HFC152A, HFC236FA, HFC365MFC, NF3, SO2F2"
        )
        extra_mhalos = "" if self._magicc_version == 6 else " plus CH2CL2, CHCL3"
        extra_totaerdirrf = (
            ""
            if self._magicc_version == 6
            else " plus NH3I i.e. direct fossil fuel ammonia forcing"
        )
        header = (
            "\n"
            "{}__RADIATIVE FORCINGS____________________________\n"
            "CONTENT:           {}\n"
            "RUN:               {}\n"
            "{: <19}{}\n"
            "DATE:              {}\n"
            "MAGICC-VERSION:    {}\n"
            "FILE PRODUCED BY:  {}\n"
            "DOCUMENTATION:     {}\n"
            "CMIP INFO:         {}\n"
            "DATABASE:          {}\n"
            "FURTHER INFO:      {}\n"
            "NOTE:              {}\n"
            "                   {}\n"
            "                   {}\n"
            "\n"
            "COLUMN_DESCRIPTION________________________________________\n"
            "1       TOTAL_INCLVOLCANIC_RF   Total anthropogenic and natural radiative forcing\n"
            "2       VOLCANIC_ANNUAL_RF      Annual mean volcanic stratospheric aerosol forcing\n"
            "3       SOLAR_RF                Solar irradiance forcing\n"
            "4       TOTAL_ANTHRO_RF         Total anthropogenic forcing\n"
            "5       GHG_RF                  Total greenhouse gas forcing (CO2, CH4, N2O, HFCs, PFCs, SF6, and Montreal Protocol gases).\n"
            "6       KYOTOGHG_RF             Total forcing from greenhouse gases controlled under the Kyoto Protocol (CO2, CH4, N2O, HFCs, PFCs, SF6).\n"
            "7       CO2CH4N2O_RF            Total forcing from CO2, methane and nitrous oxide.\n"
            "8       CO2_RF                  CO2 Forcing\n"
            "9       CH4_RF                  Methane Forcing\n"
            "10      N2O_RF                  Nitrous Oxide Forcing\n"
            "11      FGASSUM_RF              Total forcing from all flourinated gases controlled under the Kyoto Protocol (HFCs, PFCs, SF6; i.e. columns 13-24{})\n"
            "12      MHALOSUM_RF             Total forcing from all gases controlled under the Montreal Protocol (columns 25-40{})\n"
            "13-24                           Flourinated gases controlled under the Kyoto Protocol\n"
            "25-40                           Ozone Depleting Substances controlled under the Montreal Protocol\n"
            "41      TOTAER_DIR_RF           Total direct aerosol forcing (aggregating columns 42 to 47{})\n"
            "42      OCI_RF                  Direct fossil fuel aerosol (organic carbon)\n"
            "43      BCI_RF                  Direct fossil fuel aerosol (black carbon)\n"
            "44      SOXI_RF                 Direct sulphate aerosol\n"
            "45      NOXI_RF                 Direct nitrate aerosol\n"
            "46      BIOMASSAER_RF           Direct biomass burning related aerosol\n"
            "47      MINERALDUST_RF          Direct Forcing from mineral dust aerosol\n"
            "48      CLOUD_TOT_RF            Indirect aerosol effects\n"
            "49      STRATOZ_RF              Stratospheric ozone forcing\n"
            "50      TROPOZ_RF               Tropospheric ozone forcing\n"
            "51      CH4OXSTRATH2O_RF        Stratospheric water-vapour from methane oxidisation\n"
            "52      LANDUSE_RF              Landuse albedo\n"
            "53      BCSNOW_RF               Black carbon on snow.\n"
            "\n"
            "\n"
            "\n"
        ).format(
            scenario,
            meta["content"],
            scenario,
            "{} CONTACT:".format(scenario),
            meta["contact"],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            magicc_version,
            meta["file produced by"],
            meta["documentation"],
            meta["cmip info"],
            meta["database"],
            meta["further info"],
            meta["note"][0],
            meta["note"][1],
            meta["note"][2],
            extra_fgases,
            extra_mhalos,
            extra_totaerdirrf,
        )

        return header

    def _get_header_effradforcing(self):
        scenario = self.minput.get_unique_meta("scenario", no_duplicates=True)
        magicc_version = self.minput.get_unique_meta(
            "climate_model", no_duplicates=True
        )
        if magicc_version.startswith("MAGICC"):
            magicc_version = magicc_version.replace("MAGICC", "")
        else:
            raise AssertionError("climate_model should start with `MAGICC`")
        meta = self.minput.metadata
        extra_fgases = " plus C3F8, C4F10, C5F12, C7F16, C8F18, CC4F8, HFC152A, HFC236FA, HFC365MFC, NF3, SO2F2"
        extra_mhalos = " plus CH2CL2, CHCL3"
        extra_totaerdirrf = " plus NH3I i.e. direct fossil fuel ammonia forcing"
        header = (
            "\n"
            "{}__EFFECTIVE_RADIATIVE FORCINGS____________________________\n"
            "CONTENT:           {}\n"
            "RUN:               {}\n"
            "{: <19}{}\n"
            "DATE:              {}\n"
            "MAGICC-VERSION:    {}\n"
            "FILE PRODUCED BY:  {}\n"
            "DOCUMENTATION:     {}\n"
            "CMIP INFO:         {}\n"
            "DATABASE:          {}\n"
            "FURTHER INFO:      {}\n"
            "NOTE:              {}\n"
            "                   {}\n"
            "                   {}\n"
            "\n"
            "COLUMN_DESCRIPTION________________________________________\n"
            "1       TOTAL_INCLVOLCANIC_ERF   Total anthropogenic and natural effective radiative forcing\n"
            "2       VOLCANIC_ANNUAL_ERF      Annual mean volcanic stratospheric aerosol forcing\n"
            "3       SOLAR_ERF                Solar irradiance forcing\n"
            "4       TOTAL_ANTHRO_ERF         Total anthropogenic forcing\n"
            "5       GHG_ERF                  Total greenhouse gas forcing (CO2, CH4, N2O, HFCs, PFCs, SF6, and Montreal Protocol gases).\n"
            "6       KYOTOGHG_ERF             Total forcing from greenhouse gases controlled under the Kyoto Protocol (CO2, CH4, N2O, HFCs, PFCs, SF6).\n"
            "7       CO2CH4N2O_ERF            Total forcing from CO2, methane and nitrous oxide.\n"
            "8       CO2_ERF                  CO2 Forcing\n"
            "9       CH4_ERF                  Methane Forcing\n"
            "10      N2O_ERF                  Nitrous Oxide Forcing\n"
            "11      FGASSUM_ERF              Total forcing from all flourinated gases controlled under the Kyoto Protocol (HFCs, PFCs, SF6; i.e. columns 13-24{})\n"
            "12      MHALOSUM_ERF             Total forcing from all gases controlled under the Montreal Protocol (columns 25-40{})\n"
            "13-24                              Flourinated gases controlled under the Kyoto Protocol\n"
            "25-40                              Ozone Depleting Substances controlled under the Montreal Protocol\n"
            "41      TOTAER_DIR_ERF           Total direct aerosol forcing (aggregating columns 42 to 47{})\n"
            "42      OCI_ERF                  Direct fossil fuel aerosol (organic carbon)\n"
            "43      BCI_ERF                  Direct fossil fuel aerosol (black carbon)\n"
            "44      SOXI_ERF                 Direct sulphate aerosol\n"
            "45      NOXI_ERF                 Direct nitrate aerosol\n"
            "46      BIOMASSAER_ERF           Direct biomass burning related aerosol\n"
            "47      MINERALDUST_ERF          Direct Forcing from mineral dust aerosol\n"
            "48      CLOUD_TOT_ERF            Indirect aerosol effects\n"
            "49      STRATOZ_ERF              Stratospheric ozone forcing\n"
            "50      TROPOZ_ERF               Tropospheric ozone forcing\n"
            "51      CH4OXSTRATH2O_ERF        Stratospheric water-vapour from methane oxidisation\n"
            "52      LANDUSE_ERF              Landuse albedo\n"
            "53      BCSNOW_ERF               Black carbon on snow.\n"
            "\n"
            "\n"
            "\n"
        ).format(
            scenario,
            meta["content"],
            scenario,
            "{} CONTACT:".format(scenario),
            meta["contact"],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            magicc_version,
            meta["file produced by"],
            meta["documentation"],
            meta["cmip info"],
            meta["database"],
            meta["further info"],
            meta["note"][0],
            meta["note"][1],
            meta["note"][2],
            extra_fgases,
            extra_mhalos,
            extra_totaerdirrf,
        )

        return header

    def _get_header_emissions(self):
        scenario = self.minput.get_unique_meta("scenario", no_duplicates=True)
        magicc_version = self.minput.get_unique_meta(
            "climate_model", no_duplicates=True
        )
        if magicc_version.startswith("MAGICC"):
            magicc_version = magicc_version.replace("MAGICC", "")
        else:
            raise AssertionError("climate_model should start with `MAGICC`")

        meta = self.minput.metadata
        header = (
            "\n"
            "{}__EMISSIONS____________________________\n"
            "CONTENT:           {}\n"
            "RUN:               {}\n"
            "{: <19}{}\n"
            "DATE:              {}\n"
            "MAGICC-VERSION:    {}\n"
            "FILE PRODUCED BY:  {}\n"
            "DOCUMENTATION:     {}\n"
            "CMIP INFO:         {}\n"
            "DATABASE:          {}\n"
            "FURTHER INFO:      {}\n"
            "NOTE:              {}\n"
            "                   {}\n"
            "\n"
            "COLUMN_DESCRIPTION________________________________________\n"
            "1. FossilCO2        - Fossil & Industrial CO2 (Fossil, Cement, Gas Flaring & Bunker Fuels)\n"
            "2. OtherCO2         - Landuse related CO2 Emissions (CO2 emissions which change the size of the land carbon cycle pool)\n"
            "3. CH4              - Methane\n"
            "4. N2O              - Nitrous Oxide\n"
            "5. - 11.            - Tropospheric ozone precursors, aerosols and reactive gas emissions\n"
            "12. - 23.           - Flourinated gases controlled under the Kyoto Protocol, (HFCs, PFCs, SF6)\n"
            "24. - 39.           - Ozone Depleting Substances controlled under the Montreal Protocol (CFCs, HFCFC, Halons, CCl4, MCF, CH3Br, CH3Cl)\n"
            "\n"
            "\n"
        ).format(
            scenario,
            meta["content"],
            scenario,
            "{} CONTACT:".format(scenario),
            meta["contact"],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            magicc_version,
            meta["file produced by"],
            meta["documentation"],
            meta["cmip info"],
            meta["database"],
            meta["further info"],
            meta["note"][0],
            meta["note"][1],
        )

        return header

    def _get_header_concentrations(self):
        scenario = self.minput.get_unique_meta("scenario", no_duplicates=True)
        magicc_version = self.minput.get_unique_meta(
            "climate_model", no_duplicates=True
        )
        if magicc_version.startswith("MAGICC"):
            magicc_version = magicc_version.replace("MAGICC", "")
        else:
            raise AssertionError("climate_model should start with `MAGICC`")

        extra_fgases = (
            ""
            if self._magicc_version == 6
            else " and C3F8, C4F10, C5F12, C7F16, C8F18, CC4F8, HFC152A, HFC236FA, HFC365MFC, NF3, SO2F2"
        )
        extra_mhalos = "" if self._magicc_version == 6 else " and CH2CL2, CHCL3"

        meta = self.minput.metadata
        header = (
            "\n"
            "{}__MIDYEAR__CONCENTRATIONS____________________________\n"
            "CONTENT:           {}\n"
            "RUN:               {}\n"
            "{: <19}{}\n"
            "DATE:              {}\n"
            "MAGICC-VERSION:    {}\n"
            "FILE PRODUCED BY:  {}\n"
            "DOCUMENTATION:     {}\n"
            "CMIP INFO:         {}\n"
            "DATABASE:          {}\n"
            "FURTHER INFO:      {}\n"
            "NOTE:              {}\n"
            "\n"
            "COLUMN_DESCRIPTION________________________________________\n"
            "1. CO2EQ            - CO2 equivalence concentrations\n"
            "2. KYOTO-CO2EQ      - As column 1, but only aggregating greenhouse gases controlled under the Kyoto Protocol\n"
            "3. CO2              - Atmospheric CO2 concentrations\n"
            "4. CH4              - Atmospheric CH4 concentrations\n"
            "5. N2O              - Atmospheric N2O concentrations\n"
            "6. FGASSUMHFC134AEQ - All flourinated gases controlled under the Kyoto Protocol, i.e. HFCs, PFCs, and SF6 (columns 8-19{}) expressed as HFC134a equivalence concentrations.\n"
            "7. MHALOSUMCFC12EQ  - All flourinated gases controlled under the Montreal Protocol, i.e. CFCs, HCFCs, Halons, CCl4, CH3Br, CH3Cl (columns 20-35{}) expressed as CFC-12 equivalence concentrations.\n"
            "8. - 19.            - Flourinated Gases controlled under the Kyoto Protocol\n"
            "20. - 35.           - Ozone Depleting Substances controlled under the Montreal Protocol\n"
            "\n"
            "\n"
        ).format(
            scenario,
            meta["content"],
            scenario,
            "{} CONTACT:".format(scenario),
            meta["contact"],
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            magicc_version,
            meta["file produced by"],
            meta["documentation"],
            meta["cmip info"],
            meta["database"],
            meta["further info"],
            meta["note"][0],
            extra_fgases,
            extra_mhalos,
        )

        return header

    def _write_namelist(self, output):
        nml_initial, _ = self._get_initial_nml_and_data_block()
        nml = nml_initial.copy()

        # '&NML_INDICATOR' goes above, '/'' goes at end
        number_lines_nml_header_end = 2
        line_after_nml = self._newline_char

        number_col_headers = 3

        nml["THISFILE_SPECIFICATIONS"].pop("THISFILE_DATAROWS")
        nml["THISFILE_SPECIFICATIONS"].pop("THISFILE_REGIONMODE")

        nml["THISFILE_SPECIFICATIONS"]["THISFILE_FIRSTDATAROW"] = (
            len(output.getvalue().split(self._newline_char))
            + len(nml["THISFILE_SPECIFICATIONS"])
            + number_lines_nml_header_end
            + len(line_after_nml.split(self._newline_char))
            + number_col_headers
        )
        nml["THISFILE_SPECIFICATIONS"]["THISFILE_DATTYPE"] = "RCPDAT"

        if self._filepath.endswith("_RADFORCING.DAT"):
            nml["THISFILE_SPECIFICATIONS"]["THISFILE_UNITS"] = "SEE ROW 59"

        elif self._filepath.endswith("_EFFECTIVERADFORCING.DAT"):
            nml["THISFILE_SPECIFICATIONS"]["THISFILE_UNITS"] = "SEE ROW 59"

        elif self._filepath.endswith("_EMISSIONS.DAT"):
            nml["THISFILE_SPECIFICATIONS"]["THISFILE_UNITS"] = "SEE ROW 37"

        elif self._filepath.endswith("_CONCENTRATIONS.DAT"):
            nml["THISFILE_SPECIFICATIONS"]["THISFILE_UNITS"] = "SEE ROW 38"

        else:
            raise NotImplementedError

        nml["THISFILE_SPECIFICATIONS"]["THISFILE_DATACOLUMNS"] = (
            len(self._get_col_order_rename_col()[0]) - 1
        )  # exclude time column

        nml.uppercase = True
        nml._writestream(output)
        output.write(line_after_nml)

        return output

    def _write_datablock(self, output):
        _, data_block = self._get_initial_nml_and_data_block()

        drop_levels = []
        for i in range(len(data_block.columns.levels)):
            if data_block.columns.get_level_values(i)[0] not in ["VARIABLE", "UNITS"]:
                drop_levels.append(i)

        data_block.columns = data_block.columns.droplevel(drop_levels)

        for i in range(len(data_block.columns.levels)):
            if data_block.columns.get_level_values(i)[0] == "UNITS":
                units_level = i

        if self._filepath.endswith("_RADFORCING.DAT"):
            return self._write_variable_datablock_radforcing(
                output, data_block, units_level
            )

        if self._filepath.endswith("_EFFECTIVERADFORCING.DAT"):
            return self._write_variable_datablock_effradforcing(
                output, data_block, units_level
            )

        if self._filepath.endswith("_EMISSIONS.DAT"):
            return self._write_variable_datablock_emissions(
                output, data_block, units_level
            )

        if self._filepath.endswith("_CONCENTRATIONS.DAT"):
            return self._write_variable_datablock_concentrations(
                output, data_block, units_level
            )

        raise NotImplementedError

    def _write_variable_datablock_radforcing(self, output, data_block, units_level):
        data_block, units = self._reorder_data_block_and_get_units(
            data_block, units_level
        )

        units = [u.replace("W_per_msuper2", "W/m2") for u in units]

        variable_row = (
            "     YEARS  TOTAL_INCLVOLCANIC_RF  VOLCANIC_ANNUAL_RF         SOLAR_RF"
            + "".join(["{: >20}".format(v) for v in data_block.iloc[:, 4:]])
        )

        output = self._write_output(data_block, output, units, variable_row)

        return output

    def _write_variable_datablock_effradforcing(self, output, data_block, units_level):
        data_block, units = self._reorder_data_block_and_get_units(
            data_block, units_level
        )
        units = [u.replace("W_per_msuper2", "W/m2") for u in units]

        variable_row = (
            "     YEARS TOTAL_INCLVOLCANIC_ERF VOLCANIC_ANNUAL_ERF        SOLAR_ERF"
            + "".join(["{: >20}".format(v) for v in data_block.iloc[:, 4:]])
        )

        output = self._write_output(data_block, output, units, variable_row)

        return output

    def _write_variable_datablock_emissions(self, output, data_block, units_level):
        data_block, units = self._reorder_data_block_and_get_units(
            data_block, units_level
        )
        units = [u.replace("per", "/").replace("_", "") for u in units]

        variable_row = "     YEARS" + "".join(
            ["{: >20}".format(c) for c in data_block.columns[1:]]
        )

        output = self._write_output(data_block, output, units, variable_row)

        return output

    def _write_variable_datablock_concentrations(self, output, data_block, units_level):
        data_block, units = self._reorder_data_block_and_get_units(
            data_block, units_level
        )

        variable_row = "     YEARS" + "".join(
            ["{: >20}".format(c) for c in data_block.columns[1:]]
        )

        output = self._write_output(data_block, output, units, variable_row)

        return output

    def _reorder_data_block_and_get_units(self, data_block, units_level):
        col_order, rename_col = self._get_col_order_rename_col()

        metadata = data_block.columns.to_frame().reset_index(drop=True)
        metadata.columns = metadata.iloc[0]

        data_block.columns = metadata["VARIABLE"]
        data_block = data_block[col_order]

        units = metadata.set_index("VARIABLE").loc[col_order].UNITS.to_list()
        data_block.columns = data_block.columns.map(rename_col)

        return data_block, units

    def _get_col_row(self, data_block):
        return "   COLUMN:" + "".join(
            ["{: >20}".format(i) for i in range(1, (data_block.shape[1]))]
        )

    def _get_units_row(self, units):
        return "    UNITS:" + "".join(["{: >20}".format(u) for u in units[1:]])

    def _write_output(self, data_block, output, units, variable_row):
        time_col_length = 10
        time_col_format = "d"

        col_row = self._get_col_row(data_block)
        units_row = self._get_units_row(units)

        first_col_format_str = (
            "{" + ":{}{}".format(time_col_length, time_col_format) + "}"
        ).format
        other_col_format_str = "{:19.5e}".format
        formatters = [other_col_format_str] * len(data_block.columns)
        formatters[0] = first_col_format_str

        output.write(col_row)
        output.write(self._newline_char)
        output.write(units_row)
        output.write(self._newline_char)
        output.write(variable_row)
        output.write(self._newline_char)
        data_block.to_string(
            output, index=False, header=False, formatters=formatters, sparsify=False
        )
        output.write(self._newline_char)

        return output

    def _get_col_order_rename_col(self):
        if self._filepath.endswith("_RADFORCING.DAT") or self._filepath.endswith(
            "_EFFECTIVERADFORCING.DAT"
        ):
            col_order = [
                "VARIABLE",
                "TOTAL_INCLVOLCANIC_RF",
                "VOLCANIC_ANNUAL_RF",
                "SOLAR_RF",
                "TOTAL_ANTHRO_RF",
                "GHG_RF",
                "KYOTOGHG_RF",
                "CO2CH4N2O_RF",
                "CO2_RF",
                "CH4_RF",
                "N2O_RF",
                "FGASSUM_RF",
                "MHALOSUM_RF",
                "CF4_RF",
                "C2F6_RF",
                "C6F14_RF",
                "HFC23_RF",
                "HFC32_RF",
                "HFC4310_RF",
                "HFC125_RF",
                "HFC134A_RF",
                "HFC143A_RF",
                "HFC227EA_RF",
                "HFC245FA_RF",
                "SF6_RF",
                "CFC11_RF",
                "CFC12_RF",
                "CFC113_RF",
                "CFC114_RF",
                "CFC115_RF",
                "CCL4_RF",
                "CH3CCL3_RF",
                "HCFC22_RF",
                "HCFC141B_RF",
                "HCFC142B_RF",
                "HALON1211_RF",
                "HALON1202_RF",
                "HALON1301_RF",
                "HALON2402_RF",
                "CH3BR_RF",
                "CH3CL_RF",
                "TOTAER_DIR_RF",
                "OCI_RF",
                "BCI_RF",
                "SOXI_RF",
                "NOXI_RF",
                "BIOMASSAER_RF",
                "MINERALDUST_RF",
                "CLOUD_TOT_RF",
                "STRATOZ_RF",
                "TROPOZ_RF",
                "CH4OXSTRATH2O_RF",
                "LANDUSE_RF",
                "BCSNOW_RF",
            ]

            suf = "_RF"
            hfc4310_keys = ["HFC4310_RF"]
            ccl4_keys = ["CCL4_RF"]
            ch3ccl3_keys = ["CH3CCL3_RF"]
            strip_keys = [
                "CF4_RF",
                "C2F6_RF",
                "C6F14_RF",
                "HFC23_RF",
                "HFC32_RF",
                "HFC125_RF",
                "SF6_RF",
            ]
            case_keys = ["HFC134A_RF", "HFC143A_RF", "HFC227EA_RF", "HFC245FA_RF"]

            if self._filepath.endswith("_EFFECTIVERADFORCING.DAT"):
                suf = "_ERF"
                col_order = [v.replace("_RF", suf) for v in col_order]
                hfc4310_keys = [v.replace("_RF", suf) for v in hfc4310_keys]
                ccl4_keys = [v.replace("_RF", suf) for v in ccl4_keys]
                ch3ccl3_keys = [v.replace("_RF", suf) for v in ch3ccl3_keys]
                strip_keys = [v.replace("_RF", suf) for v in strip_keys]
                case_keys = [v.replace("_RF", suf) for v in case_keys]

            def rename_col(x):
                if x in hfc4310_keys:
                    return "HFC43_10"

                if x in ccl4_keys:
                    return "CARB_TET"

                if x in ch3ccl3_keys:
                    return "MCF"

                if x in strip_keys:
                    return x.replace(suf, "")

                if x in case_keys:
                    return (
                        x.replace("FA", "fa")
                        .replace("EA", "ea")
                        .replace("A", "a")
                        .replace(suf, "")
                    )

                if x.startswith("HCFC"):
                    return x.replace("HCFC", "HCFC_").replace(suf, "")

                if x.startswith("CFC"):
                    return x.replace("CFC", "CFC_").replace(suf, "")

                if x.startswith("HALON"):
                    return x.replace(suf, "")

                if x.startswith("CH3"):
                    return x.replace(suf, "")

                return x

        elif self._filepath.endswith("_EMISSIONS.DAT"):
            col_order = [
                "VARIABLE",
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
                "CFC11",
                "CFC12",
                "CFC113",
                "CFC114",
                "CFC115",
                "CCL4",
                "CH3CCL3",
                "HCFC22",
                "HCFC141B",
                "HCFC142B",
                "HALON1211",
                "HALON1202",
                "HALON1301",
                "HALON2402",
                "CH3BR",
                "CH3CL",
            ]

            def rename_col(x):
                if x == "CO2I":
                    return "FossilCO2"

                if x == "CO2B":
                    return "OtherCO2"

                if x == "SOX":
                    return "SOx"

                if x == "NOX":
                    return "NOx"

                if x == "HFC4310":
                    return "HFC43_10"

                if x == "CCL4":
                    return "CARB_TET"

                if x == "CH3CCL3":
                    return "MCF"

                if x in [
                    "HFC134A",
                    "HFC143A",
                    "HFC227EA",
                    "HFC245FA",
                ]:
                    return x.replace("FA", "fa").replace("EA", "ea").replace("A", "a")

                if x.startswith("HCFC"):
                    return x.replace("HCFC", "HCFC_")

                if x.startswith("CFC"):
                    return x.replace("CFC", "CFC_")

                return x

        elif self._filepath.endswith("_CONCENTRATIONS.DAT"):
            col_order = [
                "VARIABLE",
                "CO2EQ_CONC",
                "KYOTOCO2EQ_CONC",
                "CO2_CONC",
                "CH4_CONC",
                "N2O_CONC",
                "FGASSUMHFC134AEQ_CONC",
                "MHALOSUMCFC12EQ_CONC",
                "CF4_CONC",
                "C2F6_CONC",
                "C6F14_CONC",
                "HFC23_CONC",
                "HFC32_CONC",
                "HFC4310_CONC",
                "HFC125_CONC",
                "HFC134A_CONC",
                "HFC143A_CONC",
                "HFC227EA_CONC",
                "HFC245FA_CONC",
                "SF6_CONC",
                "CFC11_CONC",
                "CFC12_CONC",
                "CFC113_CONC",
                "CFC114_CONC",
                "CFC115_CONC",
                "CCL4_CONC",
                "CH3CCL3_CONC",
                "HCFC22_CONC",
                "HCFC141B_CONC",
                "HCFC142B_CONC",
                "HALON1211_CONC",
                "HALON1202_CONC",
                "HALON1301_CONC",
                "HALON2402_CONC",
                "CH3BR_CONC",
                "CH3CL_CONC",
            ]

            def rename_col(x):
                x = x.replace("_CONC", "")
                if x == "KYOTOCO2EQ":
                    return "KYOTO-CO2EQ"

                if x == "HFC4310":
                    return "HFC43_10"

                if x == "CCL4":
                    return "CARB_TET"

                if x == "CH3CCL3":
                    return "MCF"

                if x in [
                    "HFC134A",
                    "HFC143A",
                    "HFC227EA",
                    "HFC245FA",
                ]:
                    return x.replace("FA", "fa").replace("EA", "ea").replace("A", "a")

                if x.startswith("HCFC"):
                    return x.replace("HCFC", "HCFC_")

                if x.startswith("CFC"):
                    return x.replace("CFC", "CFC_")

                return x

        else:
            raise NotImplementedError

        return col_order, rename_col


class _MAGWriter(_Writer):
    def __init__(self, magicc_version=7):
        super().__init__(magicc_version=magicc_version)
        if self._magicc_version == 6:
            raise ValueError(".MAG files are not MAGICC6 compatible")

    def _get_header(self):
        try:
            header = self.minput.metadata.pop("header")
        except KeyError:
            warnings.warn(
                "No header detected, it will be automatically added. We recommend "
                "setting `self.metadata['header']` to ensure your files have the "
                "desired metadata."
            )
            from . import __version__

            header = "Date: {}\n" "Writer: pymagicc v{}".format(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), __version__
            )

        mdata = self.minput.metadata
        sorted_keys = sorted(mdata.keys())
        metadata = "\n".join(
            [
                "{}: {}".format(k, mdata[k])
                for k in sorted_keys
                if k not in ["timeseriestype"]  # timeseriestype goes in namelist
            ]
        )

        return (
            "---- HEADER ----\n"
            "\n"
            "{}\n"
            "\n"
            "---- METADATA ----\n"
            "\n"
            "{}\n"
            "\n".format(header, metadata)
        )

    def _get_initial_nml_and_data_block(self):
        nml, data_block = super()._get_initial_nml_and_data_block()
        try:
            ttype = self.minput.metadata["timeseriestype"]
        except KeyError:
            raise KeyError(
                "Please specify your 'timeseriestype' in "
                "`self.metadata['timeseriestype'] before writing `.MAG` files"
            )

        nml["thisfile_specifications"]["thisfile_timeseriestype"] = ttype
        if ttype not in [
            "MONTHLY",
            "POINT_START_YEAR",
            "POINT_END_YEAR",
            "POINT_MID_YEAR",
            "AVERAGE_YEAR_START_YEAR",
            "AVERAGE_YEAR_MID_YEAR",
            "AVERAGE_YEAR_END_YEAR",
        ]:
            raise ValueError("Unrecognised timeseriestype: {}".format(ttype))

        data_timeseriestype_mismatch_error = ValueError(
            "timeseriestype ({}) doesn't match data".format(
                nml["thisfile_specifications"]["thisfile_timeseriestype"]
            )
        )
        its = self.minput.timeseries()

        if ttype in ("POINT_START_YEAR", "AVERAGE_YEAR_START_YEAR"):
            if not all([v.month == 1 and v.day == 1 for v in its.columns]):
                raise data_timeseriestype_mismatch_error

        elif ttype in ("POINT_MID_YEAR", "AVERAGE_YEAR_MID_YEAR"):
            if not all([v.month == 7 and v.day == 1 for v in its.columns]):
                raise data_timeseriestype_mismatch_error

        elif ttype in ("POINT_END_YEAR", "AVERAGE_YEAR_END_YEAR"):
            if not all([v.month == 12 and v.day == 31 for v in its.columns]):
                raise data_timeseriestype_mismatch_error

        elif ttype == "MONTHLY":
            # should either be weird timesteps or 12 months per year
            if nml["thisfile_specifications"]["thisfile_annualsteps"] not in (0, 12):
                raise data_timeseriestype_mismatch_error

        # don't bother writing this as it's in the header
        nml["thisfile_specifications"].pop("thisfile_units")

        return nml, data_block

    def _check_data_filename_variable_consistency(self, data_block):
        pass  # not relevant for .MAG files

    def _get_region_order(self, data_block):
        try:
            regions = data_block.columns.get_level_values("region").tolist()
            region_order_magicc = get_region_order(regions, self._scen_7)
            region_order = convert_magicc_to_openscm_regions(region_order_magicc)
            return region_order
        except ValueError:
            abbreviations = [
                convert_magicc_to_openscm_regions(r, inverse=True) for r in set(regions)
            ]
            unrecognised_regions = [
                a
                for a in abbreviations
                if a in regions or DATA_HIERARCHY_SEPARATOR in a
            ]
            if unrecognised_regions:
                warnings.warn(
                    "Not abbreviating regions, could not find abbreviation for {}".format(
                        unrecognised_regions
                    )
                )
            return regions

    def _get_dattype_regionmode(self, regions):
        try:
            rm = get_dattype_regionmode(regions, scen7=self._scen_7)[REGIONMODE_FLAG]
        except ValueError:
            # unrecognised regionmode so write NONE
            rm = "NONE"

        return {DATTYPE_FLAG: "MAG", REGIONMODE_FLAG: rm}


def get_special_scen_code(regions, emissions):
    """
    Get special code for MAGICC6 SCEN files.

    At the top of every MAGICC6 and MAGICC5 SCEN file there is a two digit
    number. The first digit, the 'scenfile_region_code' tells MAGICC how many regions
    data is being provided for. The second digit, the 'scenfile_emissions_code', tells
    MAGICC which gases are in the SCEN file.

    The variables which are part of ``PART_OF_SCENFILE_WITH_EMISSIONS_CODE_1`` are the
    emissions species which are expected when scenfile_emissions_code is 1. Similarly,
    ``PART_OF_SCENFILE_WITH_EMISSIONS_CODE_0`` defines the emissions species which are
    expected when scenfile_emissions_code is 0.

    Having these definitions allows Pymagicc to check that the right
    set of emissions has been provided before writing SCEN files.

    Parameters
    ----------
    region : list_like
        Regions to get code for.
    emissions : list-like
        Emissions to get code for.

    Raises
    ------
    ValueError
        If the special scen code cannot be determined.

    Returns
    -------
    int
        The special scen code for the regions-emissions combination provided.
    """
    if sorted(set(PART_OF_SCENFILE_WITH_EMISSIONS_CODE_0)) == sorted(set(emissions)):
        scenfile_emissions_code = 0
    elif sorted(set(PART_OF_SCENFILE_WITH_EMISSIONS_CODE_1)) == sorted(set(emissions)):
        scenfile_emissions_code = 1
    else:
        msg = "Could not determine scen special code for emissions {}".format(emissions)
        raise ValueError(msg)

    if set(regions) == set(["WORLD"]):
        scenfile_region_code = 1
    elif set(regions) == set(["WORLD", "OECD90", "REF", "ASIA", "ALM"]):
        scenfile_region_code = 2
    elif set(regions) == set(["WORLD", "R5OECD", "R5REF", "R5ASIA", "R5MAF", "R5LAM"]):
        scenfile_region_code = 3
    elif set(regions) == set(
        ["WORLD", "R5OECD", "R5REF", "R5ASIA", "R5MAF", "R5LAM", "BUNKERS"]
    ):
        scenfile_region_code = 4
    try:
        return scenfile_region_code * 10 + scenfile_emissions_code
    except NameError:
        msg = "Could not determine scen special code for regions {}".format(regions)
        raise ValueError(msg)


class MAGICCData(ScmDataFrame):
    """
    An interface to read and write the input files used by MAGICC.

    MAGICCData can read input files from both MAGICC6 and MAGICC7. It returns
    files in a common format with a common vocabulary to simplify the process
    of reading, writing and handling MAGICC data. For more information on file
    conventions, see :ref:`magicc_file_conventions`.

    See ``notebooks/Input-Examples.ipynb`` for usage examples.

    Attributes
    ----------
    data : :obj:`pd.DataFrame`
        A pandas dataframe with the data.

    metadata : dict
        Metadata for the data in ``self.df``.

    filepath : str
        The file the data was loaded from. None if data was not loaded from a file.
    """

    def __init__(self, data, columns=None, **kwargs):
        """
        Initialise a MAGICCData instance

        Here we provide a brief over of inputs, for more details
        see ``scmdata.ScmDataFrame``.

        Parameters
        ----------
        data: pd.DataFrame, pd.Series, np.ndarray or string
            A pd.DataFrame or data file, or a numpy array of timeseries data if `columns` is specified.
            If a string is passed, data will be attempted to be read from file.

        columns: dict
            Dictionary to use to write the metadata for each timeseries in data. MAGICCData will
            also attempt to infer values from data. Any values in columns will be used in
            preference to any values found in data. The default value for "model", "scenario"
            and "climate_model" is "unspecified". See ``scmdata.ScmDataFrame`` for details.

        kwargs:
            Additional parameters passed to `pyam.core.read_files` to read non-standard files.
        """
        if not isinstance(data, str):
            self.filepath = None
            self.metadata = {}
            super().__init__(data, columns=columns, **kwargs)
        else:
            filepath = data  # assume filepath
            self.filepath = filepath
            self.metadata, data, read_columns = _read_and_return_metadata_df(filepath)
            columns = deepcopy(columns) if columns is not None else {}
            for k, v in read_columns.items():
                columns.setdefault(k, v)

            columns.setdefault("model", ["unspecified"])
            columns.setdefault("scenario", ["unspecified"])
            columns.setdefault("climate_model", ["unspecified"])

            super().__init__(data, columns=columns, **kwargs)

    def _format_datetime_col(self):
        time_srs = self["time"]
        if isinstance(time_srs.iloc[0], datetime):
            pass
        elif isinstance(time_srs.iloc[0], int):
            time_srs = [datetime(y, 1, 1) for y in to_int(time_srs)]
        else:
            time_srs = time_srs.apply(lambda x: convert_to_datetime(x))

        self["time"] = time_srs

    def _raise_not_loaded_error(self):
        raise ValueError("File has not been read from disk yet")

    @property
    def is_loaded(self):
        """bool: Whether the data has been loaded yet."""
        return self._meta is not None

    def append(self, other, inplace=False, constructor_kwargs={}, **kwargs):
        """
        Append any input which can be converted to MAGICCData to self.

        Parameters
        ----------
        other : MAGICCData, pd.DataFrame, pd.Series, str
            Source of data to append.

        inplace : bool
            If True, append ``other`` inplace, otherwise return a new ``MAGICCData``
            instance.

        constructor_kwargs : dict
            Passed to ``MAGICCData`` constructor (only used if ``other`` is not a
            ``MAGICCData`` instance).

        **kwargs
            Passed to ``super().append()``
        """
        if not isinstance(other, MAGICCData):
            other = MAGICCData(other, **constructor_kwargs)

        if inplace:
            super().append(other, inplace=inplace, **kwargs)
            # updating metadata is why we can't just use ``ScmDataFrameBase``'s append
            # method
            self.metadata.update(other.metadata)
        else:
            res = super().append(other, inplace=inplace, **kwargs)
            res.metadata = deepcopy(self.metadata)
            res.metadata.update(other.metadata)

            return res

    def write(self, filepath, magicc_version):
        """
        Write an input file to disk.

        For more information on file conventions, see :ref:`magicc_file_conventions`.

        Parameters
        ----------
        filepath : str
            Filepath of the file to write.

        magicc_version : int
            The MAGICC version for which we want to write files. MAGICC7 and MAGICC6
            namelists are incompatible hence we need to know which one we're writing
            for.
        """
        writer = determine_tool(filepath, "writer")(magicc_version=magicc_version)
        writer.write(self, filepath)


def determine_tool(filepath, tool_to_get):
    """
    Determine the tool to use for reading/writing.

    The function uses an internally defined set of mappings between filepaths,
    regular expresions and readers/writers to work out which tool to use
    for a given task, given the filepath.

    It is intended for internal use only, but is public because of its
    importance to the input/output of pymagicc.

    If it fails, it will give clear error messages about why and what the
    available regular expressions are.

    .. code:: python

        >>> mdata = MAGICCData()
        >>> mdata.read(MAGICC7_DIR, HISTRCP_CO2I_EMIS.txt)
        ValueError: Couldn't find appropriate writer for HISTRCP_CO2I_EMIS.txt.
        The file must be one of the following types and the filepath must match its corresponding regular expression:
        SCEN: ^.*\\.SCEN$
        SCEN7: ^.*\\.SCEN7$
        prn: ^.*\\.prn$

    Parameters
    ----------
    filepath : str
        Name of the file to read/write, including extension

    tool_to_get : str
        The tool to get, valid options are "reader", "writer".
        Invalid values will throw a NoReaderWriterError.
    """
    file_regexp_reader_writer = {
        "SCEN": {"regexp": r"^.*\.SCEN$", "reader": _ScenReader, "writer": _ScenWriter},
        "SCEN7": {
            "regexp": r"^.*\.SCEN7$",
            "reader": _Scen7Reader,
            "writer": _Scen7Writer,
        },
        "prn": {"regexp": r"^.*\.prn$", "reader": _PrnReader, "writer": _PrnWriter},
        # "Sector": {"regexp": r".*\.SECTOR$", "reader": _Scen7Reader, "writer": _Scen7Writer},
        "EmisIn": {
            "regexp": r"^.*\_EMIS.*\.IN$",
            "reader": _HistEmisInReader,
            "writer": _HistEmisInWriter,
        },
        "ConcIn": {
            "regexp": r"^.*\_CONC.*\.IN$",
            "reader": _ConcInReader,
            "writer": _ConcInWriter,
        },
        "OpticalThicknessIn": {
            "regexp": r"^.*\_OT\.IN$",
            "reader": _OpticalThicknessInReader,
            "writer": _OpticalThicknessInWriter,
        },
        "RadiativeForcingIn": {
            "regexp": r"^.*\_RF\.(IN|MON)$",
            "reader": _RadiativeForcingInReader,
            "writer": _RadiativeForcingInWriter,
        },
        "SurfaceTemperatureIn": {
            "regexp": r"^.*SURFACE\_TEMP\.(IN|MON)$",
            "reader": _SurfaceTemperatureInReader,
            "writer": _SurfaceTemperatureInWriter,
        },
        "Out": {
            "regexp": r"^DAT\_.*(?<!EMIS)\.OUT$",
            "reader": _OutReader,
            "writer": None,
        },
        "EmisOut": {
            "regexp": r"^DAT\_.*EMIS\.OUT$",
            "reader": _EmisOutReader,
            "writer": None,
        },
        "InverseEmis": {
            "regexp": r"^INVERSEEMIS\.OUT$",
            "reader": _InverseEmisReader,
            "writer": None,
        },
        "TempOceanLayersOut": {
            "regexp": r"^TEMP\_OCEANLAYERS.*\.OUT$",
            "reader": _TempOceanLayersOutReader,
            "writer": None,
        },
        "BinOut": {
            "regexp": r"^DAT\_.*\.BINOUT$",
            "reader": _BinaryOutReader,
            "writer": None,
        },
        "RCPData": {
            "regexp": r"^.*\.DAT",
            "reader": _RCPDatReader,
            "writer": _RCPDatWriter,
        },
        "CompactOut": {
            "regexp": r"^.*COMPACT\.OUT$",
            "reader": _CompactOutReader,
            "writer": None,
        },
        "CompactBinOut": {
            "regexp": r"^.*COMPACT\.BINOUT$",
            "reader": _BinaryCompactOutReader,
            "writer": None,
        },
        "MAG": {"regexp": r"^.*\.MAG", "reader": _MAGReader, "writer": _MAGWriter},
        # "InverseEmisOut": {"regexp": r"^INVERSEEMIS\_.*\.OUT$", "reader": _Scen7Reader, "writer": _Scen7Writer},
    }

    fbase = basename(filepath)
    if _unsupported_file(fbase):
        raise NoReaderWriterError(
            "{} is in an odd format for which we will never provide a reader/writer.".format(
                filepath
            )
        )

    for file_type, file_tools in file_regexp_reader_writer.items():
        if re.match(file_tools["regexp"], fbase):
            try:
                tool = file_tools[tool_to_get]
                if tool is None:
                    error_msg = "A {} for `{}` files is not yet implemented".format(
                        tool_to_get, file_tools["regexp"]
                    )
                    raise NotImplementedError(error_msg)

                return tool

            except KeyError:
                valid_tools = [k for k in file_tools.keys() if k != "regexp"]
                error_msg = (
                    "MAGICCData does not know how to get a {}, "
                    "valid options are: {}".format(tool_to_get, valid_tools)
                )
                raise KeyError(error_msg)

    para_file = "PARAMETERS.OUT"
    if (filepath.endswith(".CFG")) and (tool_to_get == "reader"):
        error_msg = (
            "MAGCCInput cannot read .CFG files like {}, please use "
            "pymagicc.io.read_cfg_file".format(filepath)
        )

    elif (filepath.endswith(para_file)) and (tool_to_get == "reader"):
        error_msg = (
            "MAGCCInput cannot read PARAMETERS.OUT as it is a config "
            "style file, please use pymagicc.io.read_cfg_file"
        )

    else:
        regexp_list_str = "\n".join(
            [
                "{}: {}".format(k, v["regexp"])
                for k, v in file_regexp_reader_writer.items()
            ]
        )
        error_msg = (
            "Couldn't find appropriate {} for {}.\nThe file must be one "
            "of the following types and the filepath must match its "
            "corresponding regular "
            "expression:\n{}".format(tool_to_get, fbase, regexp_list_str)
        )

    raise NoReaderWriterError(error_msg)


def _check_file_exists(file_to_read):
    if not exists(file_to_read):
        raise FileNotFoundError("Cannot find {}".format(file_to_read))


def _read_and_return_metadata_df(filepath):
    _check_file_exists(filepath)
    Reader = determine_tool(filepath, "reader")
    return Reader(filepath).read()


def read_mag_file_metadata(filepath):
    """
    Read only the metadata in a ``.MAG`` file

    This provides a way to access a ``.MAG`` file's metadata without reading the
    entire datablock, significantly reducing read time.

    Parameters
    ----------
    filepath : str
        Full path (path and name) to the file to read

    Returns
    -------
    dict
        Metadata read from the file

    Raises
    ------
    ValueError
        The file is not a ``.MAG`` file
    """
    if not filepath.endswith(".MAG"):
        raise ValueError("File must be a `.MAG` file")

    reader = _MAGReader(filepath)
    nml_start, nml_end = reader._set_lines_and_find_nml(metadata_only=True)

    return reader._derive_metadata(nml_start, nml_end)


def read_cfg_file(filepath):
    """
    Read a MAGICC ``.CFG`` file, or any other Fortran namelist

    Parameters
    ----------
    filepath : str
        Full path (path and name) to the file to read

    Returns
    -------
    :obj:`f90nml.Namelist`
        An `f90nml <https://github.com/marshallward/f90nml>`_ ``Namelist`` instance
        which contains the namelists in the file. A ``Namelist`` can be accessed just
        like a dictionary.
    """
    _check_file_exists(filepath)
    return f90nml.read(filepath)


def pull_cfg_from_parameters_out(parameters_out, namelist_to_read="nml_allcfgs"):
    """
    Pull out a single config set from a parameters_out namelist.

    This function returns a single file with the config that needs to be passed to
    MAGICC in order to do the same run as is represented by the values in
    ``parameters_out``.

    Parameters
    ----------
    parameters_out : dict, f90nml.Namelist
        The parameters to dump

    namelist_to_read : str
        The namelist to read from the file.

    Returns
    -------
    :obj:`f90nml.Namelist`
        An f90nml object with the cleaned, read out config.

    Examples
    --------
    >>> cfg = pull_cfg_from_parameters_out(magicc.metadata["parameters"])
    >>> cfg.write("/somewhere/else/ANOTHERNAME.cfg")
    """
    single_cfg = Namelist({namelist_to_read: {}})
    for key, value in parameters_out[namelist_to_read].items():
        if "file_tuning" in key:
            single_cfg[namelist_to_read][key] = ""
        else:
            try:
                if isinstance(value, str):
                    single_cfg[namelist_to_read][key] = value.strip(" \t\n\r").replace(
                        "\x00", ""
                    )
                elif isinstance(value, list):
                    clean_list = [v.strip(" \t\n\r").replace("\x00", "") for v in value]
                    single_cfg[namelist_to_read][key] = [v for v in clean_list if v]
                else:
                    if not isinstance(value, Number):
                        raise AssertionError("value is not a number: {}".format(value))

                    single_cfg[namelist_to_read][key] = value
            except AttributeError:
                if isinstance(value, list):
                    if not all([isinstance(v, Number) for v in value]):
                        raise AssertionError(
                            "List where not all values are numbers? " "{}".format(value)
                        )

                    single_cfg[namelist_to_read][key] = value
                else:
                    raise AssertionError(
                        "Unexpected cause in out parameters conversion"
                    )

    return single_cfg


def pull_cfg_from_parameters_out_file(
    parameters_out_file, namelist_to_read="nml_allcfgs"
):
    """
    Pull out a single config set from a MAGICC ``PARAMETERS.OUT`` file.

    This function reads in the ``PARAMETERS.OUT`` file and returns a single file with
    the config that needs to be passed to MAGICC in order to do the same run as is
    represented by the values in ``PARAMETERS.OUT``.

    Parameters
    ----------
    parameters_out_file : str
        The ``PARAMETERS.OUT`` file to read

    namelist_to_read : str
        The namelist to read from the file.

    Returns
    -------
    :obj:`f90nml.Namelist`
        An f90nml object with the cleaned, read out config.

    Examples
    --------
    >>> cfg = pull_cfg_from_parameters_out_file("PARAMETERS.OUT")
    >>> cfg.write("/somewhere/else/ANOTHERNAME.cfg")
    """
    parameters_out = read_cfg_file(parameters_out_file)
    return pull_cfg_from_parameters_out(
        parameters_out, namelist_to_read=namelist_to_read
    )


def get_generic_rcp_name(inname):
    """
    Convert an RCP name into the generic Pymagicc RCP name

    The conversion is case insensitive.

    Parameters
    ----------
    inname : str
        The name for which to get the generic Pymagicc RCP name

    Returns
    -------
    str
        The generic Pymagicc RCP name

    Examples
    --------
    >>> get_generic_rcp_name("RCP3PD")
    "rcp26"
    """
    # TODO: move into OpenSCM
    mapping = {
        "rcp26": "rcp26",
        "rcp3pd": "rcp26",
        "rcp45": "rcp45",
        "rcp6": "rcp60",
        "rcp60": "rcp60",
        "rcp85": "rcp85",
    }
    try:
        return mapping[inname.lower()]
    except KeyError:
        error_msg = "No generic name for input: {}".format(inname)
        raise ValueError(error_msg)


def read_scen_file(
    filepath,
    columns={
        "model": ["unspecified"],
        "scenario": ["unspecified"],
        "climate_model": ["unspecified"],
    },
    **kwargs
):
    """
    Read a MAGICC .SCEN file.

    Parameters
    ----------
    filepath : str
        Filepath of the .SCEN file to read

    columns : dict
        Passed to ``__init__`` method of MAGICCData. See
        ``MAGICCData.__init__`` for details.

    kwargs
        Passed to ``__init__`` method of MAGICCData. See
        ``MAGICCData.__init__`` for details.

    Returns
    -------
    :obj:`pymagicc.io.MAGICCData`
        ``MAGICCData`` object containing the data and metadata.
    """
    mdata = MAGICCData(filepath, columns=columns, **kwargs)

    return mdata


def _get_openscm_var_from_filepath(filepath):
    """
    Determine the OpenSCM variable from a filepath.

    Uses MAGICC's internal, implicit, filenaming conventions.

    Parameters
    ----------
    filepath : str
        Filepath from which to determine the OpenSCM variable.

    Returns
    -------
    str
        The OpenSCM variable implied by the filepath.
    """
    reader = determine_tool(filepath, "reader")(filepath)
    openscm_var = convert_magicc7_to_openscm_variables(
        convert_magicc6_to_magicc7_variables(reader._get_variable_from_filepath())
    )

    return openscm_var


def to_int(x):
    """
    Convert inputs to int and check conversion is sensible

    Parameters
    ----------
    x : :obj:`np.array`
        Values to convert

    Returns
    -------
    :obj:`np.array` of :obj:`int`
        Input, converted to int

    Raises
    ------
    ValueError
        If the int representation of any of the values is not equal to its original
        representation (where equality is checked using the ``!=`` operator).

    TypeError
        x is not a ``np.ndarray``
    """
    if not isinstance(x, np.ndarray):
        raise TypeError(
            "For our own sanity, this method only works with np.ndarray input. "
            "x is type: {}".format(type(x))
        )
    cols = np.array([int(v) for v in x])
    invalid_vals = x[cols != x]
    if invalid_vals.size:
        raise ValueError("invalid values `{}`".format(list(invalid_vals)))

    return cols


def find_parameter_groups(columns):
    """
    Find parameter groups within a list

    This finds all the parameters which should be grouped together into tuples rather
    than being separated. For example, if you have a list like
    ``["CORE_CLIMATESENSITIVITY", "RF_BBAER_DIR_WM2", "OUT_ZERO_TEMP_PERIOD_1", "OUT_ZERO_TEMP_PERIOD_2"]``,
    this function will return
    ``{"OUT_ZERO_TEMP_PERIOD": ["OUT_ZERO_TEMP_PERIOD_1", "OUT_ZERO_TEMP_PERIOD_2"]}``
    which tells you that the parameters
    ``["OUT_ZERO_TEMP_PERIOD_1", "OUT_ZERO_TEMP_PERIOD_2"]`` should be grouped
    together into a tuple with the name ``"OUT_ZERO_TEMP_PERIOD"`` while all the other
    columns don't belong to any group.

    Parameters
    ----------
    list of str
        List of strings to sort

    Returns
    -------
    dict of str: list of str
        Dictionary where the keys are the 'group names' and the values are the list of
        parameters which belong to that group name.
    """
    cols_to_merge = {}
    for c in columns:
        toks = c.split("_")
        start = "_".join(toks[:-1])
        if start.lower() in ["file_emisscen", "out_keydata", "file_tuningmodel"]:
            continue

        try:
            int(toks[-1])  # Check if the last token is an integer
            if start not in cols_to_merge:
                cols_to_merge[start] = []
            cols_to_merge[start].append(c)
        except (ValueError, TypeError):
            continue

    return {k: sorted(v) for k, v in cols_to_merge.items()}
