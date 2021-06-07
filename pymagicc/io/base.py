import re
from copy import deepcopy
from shutil import copyfileobj

import f90nml
import numpy as np
import pandas as pd
from f90nml.namelist import Namelist
from six import StringIO

from pymagicc.definitions import (
    DATA_HIERARCHY_SEPARATOR,
    convert_magicc6_to_magicc7_variables,
    convert_magicc7_to_openscm_variables,
    convert_magicc_to_openscm_regions,
    convert_pint_to_fortran_safe_units,
)
from pymagicc.magicc_time import (
    _adjust_df_index_to_match_timeseries_type,
    convert_to_decimal_year,
)
from pymagicc.utils import apply_string_substitutions

from .utils import (
    _get_openscm_var_from_filepath,
    _strip_emis_variables,
    get_dattype_regionmode,
    get_region_order,
)


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
        ch.setdefault("todo", self._default_todo_fill_value)
        ch.setdefault("climate_model", "unspecified")
        ch.setdefault("model", "unspecified")
        ch.setdefault("scenario", "unspecified")

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
        variables = _strip_emis_variables(variables)
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

    def _get_timeseries_no_nans(self):
        out = self.minput.timeseries(
            meta=["variable", "todo", "unit", "region"]
        ).T.dropna(how="all")
        if out.isnull().any().any():
            raise AssertionError(
                "Your data contains timesteps where some values are nan whilst others "
                "are not. This will not work in MAGICC."
            )

        return out

    def _get_data_block(self):
        data_block = self._get_timeseries_no_nans()
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
