from os.path import basename, exists
from shutil import copyfileobj
from copy import deepcopy
from numbers import Number
import warnings


import numpy as np
import f90nml
from f90nml.namelist import Namelist
import pandas as pd
import re
from six import StringIO


from pymagicc.utils import apply_string_substitutions
from .definitions import (
    DATTYPE_REGIONMODE_REGIONS,
    PART_OF_SCENFILE_WITH_EMISSIONS_CODE_0,
    PART_OF_SCENFILE_WITH_EMISSIONS_CODE_1,
    PART_OF_PRNFILE,
    convert_magicc_to_openscm_regions,
    convert_magicc7_to_openscm_variables,
    convert_magicc6_to_magicc7_variables,
    convert_pint_to_fortran_safe_units,
    DATA_HIERARCHY_SEPARATOR,
)


UNSUPPORTED_OUT_FILES = [
    r".*CARBONCYCLE.*OUT",
    r".*SUBANN.*BINOUT",
    r".*DAT_VOLCANIC_RF\.BINOUT",
    r".*PF\_.*OUT",
    r".*DATBASKET_.*",
    r".*INVERSE.*EMIS.*OUT",
    r".*PRECIPINPUT.*OUT",
    r".*TEMP_OCEANLAYERS.*\.BINOUT",
    r".*TIMESERIESMIX.*OUT",
    r".*SUMMARY_INDICATORS.OUT",
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
- Inverse emissions files have no units and we don't want to hardcode them
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
    """Exception raised when a valid Reader or Writer could not be found for the file
    """

    pass


class InvalidTemporalResError(ValueError):
    """Exception raised when a file has a temporal resolution which cannot be processed
    """

    pass


class _InputReader(object):
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

    def _set_lines(self):
        # TODO document this choice
        # We have to make a choice about special characters e.g. names with
        # umlauts. The standard seems to be utf-8 hence we set things up to
        # only work if the encoding is utf-8.
        with open(
            self.filepath, "r", encoding="utf-8", newline=self._newline_char
        ) as f:
            self.lines = f.readlines()

    def read(self):
        self._set_lines()

        nml_end, nml_start = self._find_nml()

        nml_values = self.process_metadata(self.lines[nml_start : nml_end + 1])

        # ignore all nml_values except units
        metadata = {key: value for key, value in nml_values.items() if key == "units"}
        metadata["header"] = "".join(self.lines[:nml_start])
        header_metadata = self.process_header(metadata["header"])
        metadata.update(header_metadata)

        # Create a stream from the remaining lines, ignoring any blank lines
        stream = StringIO()
        cleaned_lines = [l.strip() for l in self.lines[nml_end + 1 :] if l.strip()]
        stream.write("\n".join(cleaned_lines))
        stream.seek(0)

        df, metadata = self.process_data(stream, metadata)

        return metadata, df

    def _find_nml(self):
        """
        Find the start and end of the embedded namelist.

        Returns
        -------
        (int, int)
            start and end index for the namelist
        """
        nml_start = None
        nml_end = None
        for i in range(len(self.lines)):
            if self.lines[i].strip().startswith("&"):
                nml_start = i

            if self.lines[i].strip().startswith("/"):
                nml_end = i
        assert (
            nml_start is not None and nml_end is not None
        ), "Could not find namelist within {}".format(self.filepath)
        return nml_end, nml_start

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
                metadata[metadata_key] = "".join(
                    [str(v) for v in nml["THISFILE_SPECIFICATIONS"][k]]
                )
                metadata[metadata_key] = postprocess_edge_cases(metadata[metadata_key])
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
        df = self._convert_data_block_and_headers_to_df(stream, ch)
        return df, metadata

    def _convert_data_block_and_headers_to_df(self, stream, column_headers):
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

        df.index.name = "time"
        df.columns = self._get_columns_multiindex_from_column_headers(column_headers)
        df = pd.DataFrame(df.T.stack(), columns=["value"]).reset_index()

        self._convert_to_categorical_columns(df)

        return df

    def _convert_to_categorical_columns(self, df):
        for categorical_column in ["variable", "todo", "unit", "region"]:
            df[categorical_column] = df[categorical_column].astype("category")

        return df

    def _get_columns_multiindex_from_column_headers(self, ch):
        return pd.MultiIndex.from_arrays(
            [ch["variables"], ch["todos"], ch["units"], ch["regions"]],
            names=("variable", "todo", "unit", "region"),
        )

    def _get_column_headers_and_update_metadata(self, stream, metadata):
        if self._magicc7_style_header():
            column_headers, metadata = self._read_magicc7_style_header(stream, metadata)
        else:
            column_headers, metadata = self._read_magicc6_style_header(stream, metadata)

        column_headers["variables"] = convert_magicc7_to_openscm_variables(
            column_headers["variables"]
        )
        column_headers["regions"] = convert_magicc_to_openscm_regions(
            column_headers["regions"]
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
            "variables": self._read_data_header_line(
                stream, self._variable_line_keyword
            ),
            "todos": self._read_data_header_line(stream, "TODO"),
            "units": self._read_data_header_line(stream, "UNITS"),
            "regions": self._read_data_header_line(stream, "YEARS"),
        }
        metadata.pop("units")

        return column_headers, metadata

    def _read_magicc6_style_header(self, stream, metadata):
        # File written in MAGICC6 style with only one header line rest of
        # data must be inferred.
        # Note that regions header line is assumed to start with 'COLCODE'
        # or 'YEARS' instead of 'REGIONS'
        try:
            pos_regions = stream.tell()
            regions = self._read_data_header_line(stream, "COLCODE")
        except AssertionError:
            stream.seek(pos_regions)
            regions = self._read_data_header_line(stream, "YEARS")

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
            "variables": [variable] * len(regions),
            "todos": [self._default_todo_fill_value] * len(regions),
            "units": [unit] * len(regions),
            "regions": regions,
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
        for line in header.split("\n"):
            line = line.strip()
            for tag in self.header_tags:
                tag_text = "{}:".format(tag)
                if line.lower().startswith(tag_text):
                    metadata[tag] = line[len(tag_text) + 1 :].strip()

        return metadata

    def _read_data_header_line(self, stream, expected_header):
        tokens = stream.readline().split()
        assert (
            tokens[0] == expected_header
        ), "Expected a header token of {}, got {}".format(expected_header, tokens[0])
        return tokens[1:]

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
        column_headers["units"] = convert_pint_to_fortran_safe_units(
            column_headers["units"], inverse=True
        )

        for i, unit in enumerate(column_headers["units"]):
            if unit in ("W/m2", "W/m^2"):
                column_headers["units"][i] = "W / m^2"

        return column_headers


class _FourBoxReader(_InputReader):
    def _read_magicc6_style_header(self, stream, metadata):
        column_headers, metadata = super()._read_magicc6_style_header(stream, metadata)

        column_headers["regions"] = self._unify_magicc_regions(
            column_headers["regions"]
        )

        assert (
            len(set(column_headers["units"])) == 1
        ), "Only one unit should be found for a MAGICC6 style file"

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

        metadata["unit normalisation"] = column_headers["units"][0]
        column_headers["units"] = ["dimensionless"] * len(column_headers["units"])

        return column_headers, metadata

    def _read_data_header_line(self, stream, expected_header):
        tokens = super()._read_data_header_line(stream, expected_header)
        return [t.replace("OT-", "") for t in tokens]


class _RadiativeForcingInReader(_FourBoxReader):
    _regexp_capture_variable = re.compile(r".*\_(\w*\_RF)\.(IN|MON)$")

    def _read_data_header_line(self, stream, expected_header):
        tokens = super()._read_data_header_line(stream, expected_header)
        return [t.replace("FORC-", "") for t in tokens]

    # TODO: delete this in another PR
    def _read_magicc6_style_header(self, stream, metadata):
        column_headers, metadata = super()._read_magicc6_style_header(stream, metadata)

        return column_headers, metadata

    def _get_column_headers_and_update_metadata(self, stream, metadata):
        column_headers, metadata = super()._get_column_headers_and_update_metadata(
            stream, metadata
        )
        column_headers = self._read_units(column_headers)

        return column_headers, metadata


class _EmisInReader(_InputReader):
    def _read_units(self, column_headers):
        column_headers = super()._read_units(column_headers)

        units = column_headers["units"]
        variables = column_headers["variables"]
        for i, (unit, variable) in enumerate(zip(units, variables)):
            unit = unit.replace("-", "")
            if unit.startswith("Gt"):
                mass = "Gt"
            elif unit.startswith("Mt"):
                mass = "Mt"
            elif unit.startswith("kt"):
                mass = "kt"
            elif unit.startswith("t"):
                mass = "t"
            else:
                raise ValueError("Unexpected emissions unit")

            emissions_unit = unit.replace(mass, "")
            if not emissions_unit:
                emissions_unit = variable.split(DATA_HIERARCHY_SEPARATOR)[1]

            if "/" not in emissions_unit:
                # TODO: think of a way to not have to assume years...
                emissions_unit = "{} / yr".format(emissions_unit)
            else:
                emissions_unit = re.sub(r"(\S)\s?/\s?yr", r"\1 / yr", emissions_unit)

            units[i] = "{} {}".format(mass, emissions_unit)
            variables[i] = variable

        column_headers["units"] = units
        column_headers["variables"] = variables

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
        for v in column_headers["variables"]:
            # TODO: work out a way to avoid this fragile check and calling the
            # conversion once in the superclass method and again below
            if v.endswith("_EMIS") or v.startswith("Emissions"):
                tmp_vars.append(v)
            else:
                tmp_vars.append(v + "_EMIS")

        column_headers["variables"] = convert_magicc7_to_openscm_variables(tmp_vars)
        column_headers = self._read_units(column_headers)

        return column_headers, metadata


class _HistEmisInReader(_StandardEmisInReader):
    pass


class _Scen7Reader(_StandardEmisInReader):
    pass


class _NonStandardEmisInReader(_EmisInReader):
    def read(self):
        self._set_lines()
        self._stream = self._get_stream()
        header_notes_lines = self._read_header()
        df = self.read_data_block()
        header_notes_lines += self._read_notes()

        metadata = {"header": "".join(header_notes_lines)}
        metadata.update(self.process_header(metadata["header"]))

        return metadata, df

    def _get_stream(self):
        # Create a stream to work with, ignoring any blank lines
        stream = StringIO()
        cleaned_lines = [l.strip() for l in self.lines if l.strip()]
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

    def read_data_block(self):
        no_years = int(self.lines[0].strip())

        # go through datablocks until there are none left
        while True:
            ch = {}
            pos_block = self._stream.tell()
            region = convert_magicc_to_openscm_regions(self._stream.readline().strip())

            try:
                variables = convert_magicc6_to_magicc7_variables(
                    self._read_data_header_line(self._stream, "YEARS")
                )
            except IndexError:  # tried to get variables from empty string
                break
            except AssertionError:  # tried to get variables from a notes line
                break

            ch["variables"] = convert_magicc7_to_openscm_variables(
                [v + "_EMIS" for v in variables]
            )

            try:
                pos_units = self._stream.tell()
                ch["units"] = self._read_data_header_line(self._stream, "Yrs")
            except AssertionError:
                # for SRES SCEN files
                self._stream.seek(pos_units)
                ch["units"] = self._read_data_header_line(self._stream, "YEARS")

            ch = self._read_units(ch)
            ch["todos"] = ["SET"] * len(variables)
            ch["regions"] = [region] * len(variables)

            region_block = StringIO()
            for i in range(no_years):
                region_block.write(self._stream.readline())
            region_block.seek(0)

            region_df = self._convert_data_block_and_headers_to_df(region_block, ch)

            try:
                df = pd.concat([region_df, df], axis="rows")
            except NameError:
                df = region_df

        self._stream.seek(pos_block)

        return self._convert_to_categorical_columns(df)

    def _read_notes(self):
        notes = []
        while True:
            line = self._stream.readline()
            if not line:
                break
            notes.append(line)

        return notes


class _PrnReader(_NonStandardEmisInReader):
    def read(self):
        metadata, df = super().read()

        # now fix labelling, have to copy index :(
        variables = df.columns.get_level_values("VARIABLE").tolist()
        variables = convert_magicc6_to_magicc7_variables(variables)
        todos = ["SET"] * len(variables)
        region = convert_magicc_to_openscm_regions("WORLD")

        concs = False
        emms = False
        if "unit" in metadata:
            if metadata["unit"] == "ppt":
                concs = True
            elif metadata["unit"] == "metric tons":
                emms = True
            else:
                error_msg = "I do not recognise the unit, {}, in file{}".format(
                    metadata["unit"], self.filepath
                )
                raise ValueError(error_msg)
        else:
            # just have to assume global emissions in tons
            emms = True

        if concs:
            unit = "ppt"
            variables = [v + "_CONC" for v in variables]
        elif emms:
            unit = "t"
            variables = [v + "_EMIS" for v in variables]

        column_headers = {
            "variables": convert_magicc7_to_openscm_variables(variables),
            "todos": todos,
            "units": [unit] * len(variables),
            "regions": [region] * len(variables),
        }
        if emms:
            column_headers = self._read_units(column_headers)

        df.columns = self._get_columns_multiindex_from_column_headers(column_headers)
        df = pd.DataFrame(df.T.stack(), columns=["value"]).reset_index()
        df = self._convert_to_categorical_columns(df)

        for k in ["gas", "unit"]:
            try:
                metadata.pop(k)
            except KeyError:
                pass

        return metadata, df

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
        # read out the header
        data_block_header_line = self._stream.readline()
        variables = []
        col_width = 10
        for n in np.arange(0, len(data_block_header_line), col_width):
            pos = int(n)
            variable = data_block_header_line[pos : pos + col_width].strip()
            if variable != "Years":
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
        df.columns = pd.MultiIndex.from_arrays(
            [variables, todos, units, regions],
            names=("VARIABLE", "TODO", "UNITS", "REGION"),
        )

        # put stream back for notes reading
        self._stream.seek(prev_pos)

        return df

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


class _TempOceanLayersOutReader(_InputReader):
    _regexp_capture_variable = re.compile(r"(TEMP\_OCEANLAYERS\_?\w*)\.OUT$")
    _default_todo_fill_value = "N/A"

    def _read_magicc6_style_header(self, stream, metadata):
        column_headers, metadata = super()._read_magicc6_style_header(stream, metadata)

        if set(column_headers["variables"]) == {"TEMP_OCEANLAYERS"}:
            region = "GLOBAL"
        elif set(column_headers["variables"]) == {"TEMP_OCEANLAYERS_NH"}:
            region = "NHOCEAN"
        elif set(column_headers["variables"]) == {"TEMP_OCEANLAYERS_SH"}:
            region = "SHOCEAN"
        else:
            self._raise_cannot_determine_variable_from_filepath_error()

        column_headers["variables"] = [
            "OCEAN_TEMP_" + l for l in column_headers["regions"]
        ]
        column_headers["regions"] = [region] * len(column_headers["regions"])

        return column_headers, metadata


class _BinData(object):
    def __init__(self, filepath):
        # read the entire file into memory
        self.data = open(filepath, "rb").read()
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

        assert (
            self.data[self.pos + 4 + size : self.pos + 4 + size + 4].cast("i")[0]
            == size
        )
        self.pos = self.pos + 4 + size + 4

        res = np.array(d.cast(t))

        # Return as a scalar or a numpy array if it is an array
        if res.size == 1:
            return res[0]
        return res


class _BinaryOutReader(_InputReader):
    _regexp_capture_variable = re.compile(r"DAT\_(.*)\.BINOUT$")
    _default_todo_fill_value = "N/A"

    def read(self):
        # Read the entire file into memory
        data = _BinData(self.filepath)

        metadata = self.process_header(data)
        df, metadata = self.process_data(data, metadata)

        return metadata, df

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

        assert len(globe) == len(index)

        regions = stream.read_chunk("d")
        num_regions = int(len(regions) / len(index))
        regions = regions.reshape((-1, num_regions), order="F")

        data = np.concatenate((globe[:, np.newaxis], regions), axis=1)

        df = pd.DataFrame(data, index=index)

        if isinstance(df.index, pd.core.indexes.numeric.Float64Index):
            df.index = df.index.to_series().round(3)

        df.index.name = "time"

        regions = [
            "World",
            "World|Northern Hemisphere|Ocean",
            "World|Northern Hemisphere|Land",
            "World|Southern Hemisphere|Ocean",
            "World|Southern Hemisphere|Land",
        ]

        variable = convert_magicc6_to_magicc7_variables(
            self._get_variable_from_filepath()
        )
        variable = convert_magicc7_to_openscm_variables(variable)
        column_headers = {
            "variables": [variable] * (num_regions + 1),
            "regions": regions,
            "units": ["unknown"] * len(regions),
            "todos": ["SET"] * len(regions),
        }
        df.columns = self._get_columns_multiindex_from_column_headers(column_headers)
        df = pd.DataFrame(df.T.stack(), columns=["value"]).reset_index()
        df = self._convert_to_categorical_columns(df)

        return df, metadata

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
                "{}: Only annual binary files can currently be processed".format(
                    self.filepath
                )
            )

        return metadata


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
    dattype_flag = "THISFILE_DATTYPE"
    regionmode_flag = "THISFILE_REGIONMODE"
    region_dattype_row = _get_dattype_regionmode_regions_row(regions, scen7=scen7)

    dattype = DATTYPE_REGIONMODE_REGIONS[dattype_flag.lower()][region_dattype_row].iloc[
        0
    ]
    regionmode = DATTYPE_REGIONMODE_REGIONS[regionmode_flag.lower()][
        region_dattype_row
    ].iloc[0]

    return {dattype_flag: dattype, regionmode_flag: regionmode}


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
    assert sum(region_dattype_row) == 1

    return region_dattype_row


class _InputWriter(object):
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
        # TODO: make copy attribute for MAGICCData
        self.minput = type(magicc_input)()
        self.minput.df = magicc_input.df.copy()
        self.minput.metadata = deepcopy(magicc_input.metadata)

        # pivot the data table before moving on
        self.minput.df = self.minput.df.pivot_table(
            values="value", index="time", columns=["variable", "todo", "unit", "region"]
        )

        output = StringIO()

        output = self._write_header(output)
        output = self._write_namelist(output)
        output = self._write_datablock(output)

        with open(
            filepath, "w", encoding="utf-8", newline=self._newline_char
        ) as output_file:
            output.seek(0)
            copyfileobj(output, output_file)

    def _write_header(self, output):
        output.write(self._get_header() + 2 * self._newline_char)
        return output

    def _get_header(self):
        return self.minput.metadata["header"]

    def _write_namelist(self, output):
        nml_initial, data_block = self._get_initial_nml_and_data_block()
        nml = nml_initial.copy()

        # '&NML_INDICATOR' goes above, '/'' goes at end
        no_lines_nml_header_end = 2
        line_after_nml = self._newline_char

        try:
            no_col_headers = len(data_block.columns.levels)
        except AttributeError:
            assert isinstance(data_block.columns, pd.core.indexes.base.Index)
            no_col_headers = 1

        if self._magicc_version == 6:
            nml["THISFILE_SPECIFICATIONS"].pop("THISFILE_REGIONMODE")
            nml["THISFILE_SPECIFICATIONS"].pop("THISFILE_DATAROWS")

        nml["THISFILE_SPECIFICATIONS"]["THISFILE_FIRSTDATAROW"] = (
            len(output.getvalue().split(self._newline_char))
            + len(nml["THISFILE_SPECIFICATIONS"])
            + no_lines_nml_header_end
            + len(line_after_nml.split(self._newline_char))
            + no_col_headers
        )

        nml.uppercase = True
        nml._writestream(output)
        output.write(line_after_nml)

        return output

    def _write_datablock(self, output):
        nml_initial, data_block = self._get_initial_nml_and_data_block()

        # for most data files, as long as the data is space separated, the
        # format doesn't matter
        time_col_length = 12
        if nml_initial["THISFILE_SPECIFICATIONS"]["THISFILE_ANNUALSTEPS"] > 1:
            time_col_format = "f"
        else:
            time_col_format = "d"

        first_col_format_str = (
            "{" + ":{}{}".format(time_col_length, time_col_format) + "}"
        ).format
        other_col_format_str = "{:18.5e}".format
        # I have no idea why these spaces are necessary at the moment, something wrong with pandas...?
        pd_pad = " " * (
            time_col_length - len(data_block.columns.get_level_values(0)[0]) - 1
        )
        output.write(pd_pad)
        formatters = [other_col_format_str] * len(data_block.columns)
        formatters[0] = first_col_format_str
        data_block.to_string(output, index=False, formatters=formatters, sparsify=False)
        output.write(self._newline_char)
        return output

    def _get_initial_nml_and_data_block(self):
        data_block = self._get_data_block()

        regions = convert_magicc_to_openscm_regions(
            data_block.columns.get_level_values("region").tolist(), inverse=True
        )
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

        number_years = (
            nml["THISFILE_SPECIFICATIONS"]["THISFILE_LASTYEAR"]
            - nml["THISFILE_SPECIFICATIONS"]["THISFILE_FIRSTYEAR"]
            + 1
        )
        annual_steps = int(len(data_block) / number_years)
        nml["THISFILE_SPECIFICATIONS"]["THISFILE_ANNUALSTEPS"] = (
            annual_steps if annual_steps % 1 == 0 else 0
        )

        units_unique = list(set(self._get_df_header_row("unit")))
        nml["THISFILE_SPECIFICATIONS"]["THISFILE_UNITS"] = (
            convert_pint_to_fortran_safe_units(units_unique[0])
            if len(units_unique) == 1
            else "MISC"
        )

        nml["THISFILE_SPECIFICATIONS"].update(
            get_dattype_regionmode(regions, scen7=self._scen_7)
        )

        return nml, data_block

    def _get_data_block(self):
        data_block = self.minput.df.copy()
        # probably not necessary but a sensible check
        assert data_block.columns.names == ["variable", "todo", "unit", "region"]

        regions = data_block.columns.get_level_values("region").tolist()
        try:
            region_order_magicc = get_region_order(regions, self._scen_7)
        except AssertionError:
            # this deals with the ridiculous case where we need to rename SCEN regions
            # to SCEN7 regions because the regions ["WORLD", "R5ASIA", "R5LAM",
            # "R5REF", "R5REF", "R5OECD", "BUNKERS"] don't exist in MAGICC7
            assumed_mapping = {
                "World": "World",
                "World|R5ASIA": "World|R6ASIA",
                "World|R5REF": "World|R6REF",
                "World|R5LAM": "World|R6LAM",
                "World|R5MAF": "World|R6MAF",
                "World|R5OECD": "World|R6OECD90",
                "World|Bunkers": "World|Bunkers",
            }
            data_block = data_block.rename(
                assumed_mapping, axis="columns", level="region"
            )
            regions = data_block.columns.get_level_values("region").tolist()
            region_order_magicc = get_region_order(regions, self._scen_7)
            warn_msg = (
                "Writing SCEN7 file with RCP regions, assuming directly renaming to "
                "MAGICC7 regions is ok"
            )
            warnings.warn(warn_msg)

        region_order = convert_magicc_to_openscm_regions(region_order_magicc)
        data_block = data_block.reindex(region_order, axis=1, level="region")

        return data_block

    def _get_df_header_row(self, col_name):
        return self.minput.df.columns.get_level_values(col_name).tolist()


class _ConcInWriter(_InputWriter):
    pass


class _OpticalThicknessInWriter(_InputWriter):
    pass


class _RadiativeForcingInWriter(_InputWriter):
    pass


class _HistEmisInWriter(_InputWriter):
    _variable_header_row_name = "GAS"

    def _get_df_header_row(self, col_name):
        hr = super()._get_df_header_row(col_name)
        return [v.replace("_EMIS", "") for v in hr]


class _Scen7Writer(_HistEmisInWriter):
    _scen_7 = True


class _PrnWriter(_InputWriter):
    def _write_header(self, output):
        output.write(self._get_header())
        return output

    def _write_namelist(self, output):
        return output

    def _write_datablock(self, output):
        lines = output.getvalue().split(self._newline_char)
        data_block = self._get_data_block()

        units = self.minput.df.columns.get_level_values("unit").unique()
        unit = units[0].split(" ")[0]
        if unit == "t":
            assert all(
                [u.startswith("t ") and u.endswith(" / yr") for u in units]
            ), "Prn emissions file with non tonne per year units won't work"
            lines.append("Unit: metric tons")
            other_col_format_str = "{:9.0f}".format
        elif unit == "ppt":
            assert all(
                [u == "ppt" for u in units]
            ), "Prn concentrations file with non ppt units won't work"
            lines.append("Unit: {}".format(unit))
            other_col_format_str = "{:9.3e}".format
        else:
            raise ValueError("Unit of {} is not recognised for prn file".format(unit))

        # line with number of rows to skip, start year and end year
        no_indicator_lines = 1
        no_blank_lines_after_indicator = 1

        no_header_lines = len(lines)
        no_blank_lines_after_header = 1

        data_block_header_rows = 1

        # we don't need other blank lines as they're skipped in source anyway
        line_above_data_block = (
            no_indicator_lines
            + no_blank_lines_after_indicator
            + no_header_lines
            + no_blank_lines_after_header
            + data_block_header_rows
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
        time_col_length = 12
        first_col_format_str = ("{" + ":{}d".format(time_col_length) + "}").format

        formatters = [other_col_format_str] * len(data_block.columns)
        formatters[0] = first_col_format_str

        col_headers = data_block.columns.tolist()
        first_pad = " " * (time_col_length - len(col_headers[0]))
        col_header = first_pad + "".join(["{:10}".format(c) for c in col_headers])
        lines.append(col_header)

        data_block_str = data_block.to_string(
            index=False, header=False, formatters=formatters, sparsify=False
        )

        lines.append(data_block_str)
        output.seek(0)
        output.write(self._newline_char.join(lines))

        return output

    def _get_data_block(self):
        data_block = self.minput.df.copy()

        data_block.columns = data_block.columns.get_level_values("variable")
        magicc7_vars = convert_magicc7_to_openscm_variables(
            data_block.columns.get_level_values("variable"), inverse=True
        )

        old_style_vars = [
            v.replace("_EMIS", "").replace("_CONC", "") for v in magicc7_vars
        ]
        data_block.columns = old_style_vars

        emms_assert_msg = (
            "Prn files must have, and only have, "
            "the following species: ".format(PART_OF_PRNFILE)
        )
        assert set(data_block.columns) == set(PART_OF_PRNFILE), emms_assert_msg

        data_block.index.name = "Years"

        data_block.reset_index(inplace=True)

        return data_block


class _ScenWriter(_InputWriter):
    def _write_header(self, output):
        header_lines = []
        header_lines.append("{}".format(len(self.minput.df)))

        variables = self._get_df_header_row("variable")
        variables = convert_magicc7_to_openscm_variables(variables, inverse=True)
        variables = [v.replace("_EMIS", "") for v in variables]

        regions = self._get_df_header_row("region")
        regions = convert_magicc_to_openscm_regions(regions, inverse=True)

        special_scen_code = get_special_scen_code(regions=regions, emissions=variables)

        header_lines.append("{}".format(special_scen_code))

        # for a scen file, the convention is (although all these lines are
        # actually ignored by source so could be anything):
        # - line 3 is name
        # - line 4 is description
        # - line 5 is notes (other notes lines go at the end)
        # - line 6 is empty
        header_lines.append("NAME - need better solution for how to control this")
        header_lines.append(
            "DESCRIPTION - need better solution for how to control this"
        )
        header_lines.append("NOTES - need better solution for how to control this")
        header_lines.append("")

        header_lines.append(
            "OTHER NOTES - need better solution for how to control this"
        )
        header_lines.append(
            "OTHER NOTES - need better solution for how to control this"
        )
        header_lines.append(
            "OTHER NOTES - need better solution for how to control this"
        )
        header_lines.append(
            "OTHER NOTES - need better solution for how to control this"
        )

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
        no_notes_lines = len(lines) - 6

        def _gip(lines, no_notes_lines):
            """
            Get the point where we should insert the data block.
            """
            return len(lines) - no_notes_lines

        region_order = get_region_order(
            self._get_df_header_row("region"), scen7=self._scen_7
        )
        # format is vitally important for SCEN files as far as I can tell
        time_col_length = 12
        first_col_format_str = ("{" + ":{}d".format(time_col_length) + "}").format
        other_col_format_str = "{:10.4f}".format

        # TODO: doing it this way, out of the loop,  should ensure things
        # explode if your regions don't all have the same number of emissions
        # timeseries or does extra timeseries in there (that probably
        # shouldn't raise an error, another one for the future), although the
        # explosion will be cryptic so should add a test for good error
        # message at some point
        formatters = [other_col_format_str] * (
            int(len(self.minput.df.columns) / len(region_order))
            + 1  # for the years column
        )
        formatters[0] = first_col_format_str

        # we need this to do the variable ordering
        regions = convert_magicc_to_openscm_regions(
            self._get_df_header_row("region"), inverse=True
        )
        variables = convert_magicc7_to_openscm_variables(
            self._get_df_header_row("variable"), inverse=True
        )
        variables = [v.replace("_EMIS", "") for v in variables]

        special_scen_code = get_special_scen_code(regions=regions, emissions=variables)
        if special_scen_code % 10 == 0:
            variable_order = PART_OF_SCENFILE_WITH_EMISSIONS_CODE_0
        else:
            variable_order = PART_OF_SCENFILE_WITH_EMISSIONS_CODE_1

        for region in region_order:
            region_block_region = convert_magicc_to_openscm_regions(region)
            region_block = self.minput.df.xs(
                region_block_region, axis=1, level="region", drop_level=False
            )
            region_block.columns = region_block.columns.droplevel("todo")
            region_block.columns = region_block.columns.droplevel("region")

            variables = region_block.columns.get_level_values("variable").tolist()
            variables = convert_magicc7_to_openscm_variables(variables, inverse=True)
            region_block.columns = region_block.columns.set_levels(
                levels=[v.replace("_EMIS", "") for v in variables], level="variable"
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
            units = [u.replace("peryr", "") for u in units]

            assert region_block.columns.names == ["variable", "unit"]
            region_block = region_block.rename(columns=str).reset_index()
            region_block.columns = [["YEARS"] + variables, ["Yrs"] + units]

            # I have no idea why these spaces are necessary at the moment, something wrong with pandas...?
            pd_pad = " " * (
                time_col_length - len(region_block.columns.get_level_values(0)[0]) - 1
            )
            region_block_str = region + self._newline_char
            region_block_str += pd_pad
            region_block_str += region_block.to_string(
                index=False, formatters=formatters, sparsify=False
            )
            region_block_str += self._newline_char * 2

            lines.insert(_gip(lines, no_notes_lines), region_block_str)

        output.seek(0)
        output.write(self._newline_char.join(lines))
        return output


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


class MAGICCData(object):
    """
    An interface to read and write the input files used by MAGICC.

    MAGICCData can read input files from both MAGICC6 and MAGICC7. It returns
    files in a common format with a common vocabulary to simplify the process
    of reading, writing and handling MAGICC data.

    MAGICCData, once the target input file has been loaded, can be
    treated as a Pandas DataFrame. All the methods available to a DataFrame
    can be called on MAGICCData.

    .. code:: python

        with MAGICC6() as magicc:
            mdata = MAGICCData("HISTRCP_CO2I_EMIS.IN")
            mdata.read(magicc.run_dir)
            mdata.plot()

    A MAGICCData instance can also be used to write files e.g.

    .. code:: python

        with MAGICC6() as magicc:
            mdata = MAGICCData("HISTRCP_CO2I_EMIS.IN")
            mdata.read(magicc.run_dir)
            mdata.write("EXAMPLE_CO2I_EMIS.IN", "./")

    See ``notebooks/Input-Examples.ipynb`` for further usage examples.

    Parameters
    ----------
    filepath : str
        Optional file name, including extension, for the target
        file, i.e. 'HISTRCP_CO2I_EMIS.IN'. The file is not read until the search
        directory is provided in ``read``. This allows for MAGICCData files to be
        lazy-loaded once the appropriate MAGICC run directory is known.

    Attributes
    ----------
    df : :obj:`pd.DataFrame`
        A pandas dataframe with the data.
    metadata : dict
        Metadata for the data in ``self.df``.
    filepath : str
        The file the data was loaded from.
    """

    def __init__(self):
        """
        Initialise a MAGICCData object.
        """
        self.df = None
        self.metadata = {}
        self.filepath = None

    def __getitem__(self, item):
        """
        Allow for lazy loading.
        """
        if not self.is_loaded:
            self._raise_not_loaded_error()
        return self[item]

    def __getattr__(self, item):
        """
        Proxy any attributes/functions on the dataframe.
        """
        if not self.is_loaded:
            self._raise_not_loaded_error()
        return getattr(self.df, item)

    def _raise_not_loaded_error(self):
        raise ValueError("File has not been read from disk yet")

    @property
    def is_loaded(self):
        """bool: Whether the data has been loaded yet."""
        return self.df is not None

    def read(self, filepath):
        """
        Read an input file from disk.

        The resulting data is assigned to the ``df`` attribute of ``self`` whilst the
        metadata is stored in the ``metadata`` attribute.

        Parameters
        ----------
        filepath : str
            Filepath of the file to read.
        """
        _check_file_exists(filepath)
        self.metadata, self.df = self._read_and_return_metadata_df(filepath)

    def _read_and_return_metadata_df(self, filepath):
        reader = self.determine_tool(filepath, "reader")(filepath)
        return reader.read()

    def append(self, filepath):
        """
        Append data from an input file read from disk.

        Thre resulting data will be appended to the ``df`` attribute of ``self``
        whilst the metadata is stored in the ``metadata`` attribute. If ``self``
        currently contains no data, the read data will simply be assigned to the
        relevant attributes of ``self``.

        Parameters
        ----------
        filepath : str, list of str
            Filepath(s) of the file to read.
        """
        filepath = [filepath] if isinstance(filepath, str) else filepath

        dfs_to_add = [] if self.df is None else [self.df]

        for fp in filepath:
            metadata_to_add, df_to_add = self._read_and_return_metadata_df(fp)

            self.metadata.update(metadata_to_add)
            dfs_to_add.append(df_to_add)

        self.df = pd.concat(dfs_to_add)

    def write(self, filepath, magicc_version):
        """
        Write an input file to disk.

        Parameters
        ----------
        filepath : str
            Filepath of the file to write.

        magicc_version : int
            The MAGICC version for which we want to write files. MAGICC7 and MAGICC6
            namelists are incompatible hence we need to know which one we're writing
            for.
        """
        writer = self.determine_tool(filepath, "writer")(magicc_version=magicc_version)
        writer.write(self, filepath)

    def determine_tool(self, filepath, tool_to_get):
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
            "SCEN": {
                "regexp": r"^.*\.SCEN$",
                "reader": _ScenReader,
                "writer": _ScenWriter,
            },
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
            "Out": {"regexp": r"^DAT\_.*\.OUT$", "reader": _OutReader, "writer": None},
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
            # "InverseEmisOut": {"regexp": r"^INVERSEEMIS\_.*\.OUT$", "reader": _Scen7Reader, "writer": _Scen7Writer},
        }

        fbase = basename(filepath)
        for file_type, file_tools in file_regexp_reader_writer.items():
            if re.match(file_tools["regexp"], fbase):
                try:
                    return file_tools[tool_to_get]
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

        elif _unsupported_file(filepath):
            error_msg = "{} is in an odd format for which we will never provide a reader/writer.".format(
                filepath
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


def read_cfg_file(filepath):
    """Read a MAGICC ``.CFG`` file, or any other Fortran namelist

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
    """Pull out a single config set from a parameters_out namelist.

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
                    assert isinstance(value, Number)
                    single_cfg[namelist_to_read][key] = value
            except AttributeError:
                if isinstance(value, list):
                    assert all([isinstance(v, Number) for v in value])
                    single_cfg[namelist_to_read][key] = value
                else:
                    raise AssertionError(
                        "Unexpected cause in out parameters conversion"
                    )

    return single_cfg


def pull_cfg_from_parameters_out_file(
    parameters_out_file, namelist_to_read="nml_allcfgs"
):
    """Pull out a single config set from a MAGICC ``PARAMETERS.OUT`` file.

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
