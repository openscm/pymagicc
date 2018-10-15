from os.path import basename, exists, join
from shutil import copyfileobj
from copy import deepcopy

import numpy as np
import f90nml
from f90nml.namelist import Namelist
import pandas as pd
import re
from six import StringIO

from pymagicc import MAGICC6

# Not used yet:
# emissions_units,
# concentrations_units,
from .definitions import (
    dattype_regionmode_regions,
    scen_emms_code_0,
    scen_emms_code_1,
    prn_species,
)


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
    ]
    _newline_char = "\n"
    _variable_line_keyword = "VARIABLE"
    _regexp_capture_variable = None

    def __init__(self, filename):
        self.filename = filename

    def _set_lines(self):
        # TODO document this choice
        # We have to make a choice about special characters e.g. names with
        # umlauts. The standard seems to be utf-8 hence we set things up to
        # only work if the encoding is utf-8.
        with open(
            self.filename, "r", encoding="utf-8", newline=self._newline_char
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
        ), "Could not find namelist within {}".format(self.filename)
        return nml_end, nml_start

    def process_metadata(self, lines):
        # TODO: replace with f90nml.reads when released (>1.0.2)
        parser = f90nml.Parser()
        nml = parser._readstream(lines, {})
        # If there's a hyphen in the value, it gets split (which I think is
        # sensible behaviour for Fortran as having hyphens in stuff is asking
        # for trouble), hence we have to join everything back together
        # this breaks if units has a '/' in it, not sure how to fix...
        metadata = {}
        for k in nml["THISFILE_SPECIFICATIONS"]:
            metadata_key = k.split("_")[1]
            try:
                metadata[metadata_key] = "".join(nml["THISFILE_SPECIFICATIONS"][k])
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
        ch, metadata = self._get_column_headers_update_metadata(stream, metadata)

        df = pd.read_csv(
            stream,
            skip_blank_lines=True,
            delim_whitespace=True,
            header=None,
            index_col=0,
        )

        if isinstance(df.index, pd.core.indexes.numeric.Float64Index):
            df.index = df.index.to_series().round(3)

        df.index.name = "YEAR"
        df.columns = pd.MultiIndex.from_arrays(
            [ch["variables"], ch["todos"], ch["units"], ch["regions"]],
            names=("VARIABLE", "TODO", "UNITS", "REGION"),
        )

        return df, metadata

    def _get_column_headers_update_metadata(self, stream, metadata):
        if self._magicc7_style_header():
            column_headers, metadata = self._read_magicc7_style_header(stream, metadata)
        else:
            column_headers, metadata = self._read_magicc6_style_header(stream, metadata)

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

        column_headers = {
            "variables": [self._get_variable_from_filename()] * len(regions),
            "todos": ["SET"] * len(regions),
            "units": [unit] * len(regions),
            "regions": regions,
        }

        for k in ["unit", "units", "gas"]:
            try:
                metadata.pop(k)
            except KeyError:
                pass

        return column_headers, metadata

    def _get_variable_from_filename(self):
        """
        Determine the file variable from the filename.

        Returns
        -------
        str
            Best guess of variable name from the filename
        """
        try:
            return self.regexp_capture_variable.search(self.filename).group(1)
        except AttributeError:
            self._raise_cannot_determine_variable_from_filename_error()

    @property
    def regexp_capture_variable(self):
        if self._regexp_capture_variable is None:
            raise NotImplementedError()
        return self._regexp_capture_variable

    def _raise_cannot_determine_variable_from_filename_error(self):
        error_msg = "Cannot determine variable from filename: {}".format(self.filename)
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

    def _map_magicc_regions(self, regions):
        region_mapping = {
            "GLOBAL": "GLOBAL",
            "NO": "NHOCEAN",
            "SO": "SHOCEAN",
            "NL": "NHLAND",
            "SL": "SHLAND",
        }
        return [region_mapping[r] for r in regions]


class _NonEmisInReader(_InputReader):
    def _read_magicc6_style_header(self, stream, metadata):
        column_headers, metadata = super()._read_magicc6_style_header(stream, metadata)

        column_headers["regions"] = self._map_magicc_regions(column_headers["regions"])

        assert (
            len(set(column_headers["units"])) == 1
        ), "Only one unit should be found for a MAGICC6 style file"

        return column_headers, metadata


class _ConcInReader(_NonEmisInReader):
    _regexp_capture_variable = re.compile(r".*\_(\w*\-?\w*\_CONC)\.IN$")

    def _get_variable_from_filename(self):
        variable = super()._get_variable_from_filename()
        return _convert_magicc6_to_magicc7_variables(variable)

    def _read_data_header_line(self, stream, expected_header):
        tokens = super()._read_data_header_line(stream, expected_header)
        return [t.replace("_MIXINGRATIO", "") for t in tokens]


class _OpticalThicknessInReader(_NonEmisInReader):
    _regexp_capture_variable = re.compile(r".*\_(\w*\_OT)\.IN$")

    def _read_magicc6_style_header(self, stream, metadata):
        column_headers, metadata = super()._read_magicc6_style_header(stream, metadata)

        metadata["unit normalisation"] = column_headers["units"][0]
        column_headers["units"] = ["DIMENSIONLESS"] * len(column_headers["units"])

        return column_headers, metadata

    def _read_data_header_line(self, stream, expected_header):
        tokens = super()._read_data_header_line(stream, expected_header)
        return [t.replace("OT-", "") for t in tokens]


class _RadiativeForcingInReader(_NonEmisInReader):
    _regexp_capture_variable = re.compile(r".*\_(\w*\_RF)\.(IN|MON)$")

    def _read_data_header_line(self, stream, expected_header):
        tokens = super()._read_data_header_line(stream, expected_header)
        return [t.replace("FORC-", "") for t in tokens]

    def _read_magicc6_style_header(self, stream, metadata):
        column_headers, metadata = super()._read_magicc6_style_header(stream, metadata)

        return column_headers, metadata


class _EmisInReader(_InputReader):
    _regexp_capture_variable = re.compile(r".*\_(\w*\_EMIS)\.IN$")
    _variable_line_keyword = "GAS"

    def _read_data_header_line(self, stream, expected_header):
        tokens = super()._read_data_header_line(stream, expected_header)
        return [t.replace("EMIS-", "") for t in tokens]

    def _get_column_headers_update_metadata(self, stream, metadata):
        column_headers, metadata = super()._get_column_headers_update_metadata(
            stream, metadata
        )

        tmp_vars = []
        for v in column_headers["variables"]:
            if v.endswith("_EMIS"):
                tmp_vars.append(v)
            else:
                tmp_vars.append(v + "_EMIS")

        column_headers["variables"] = tmp_vars

        return column_headers, metadata


class _HistEmisInReader(_EmisInReader):
    pass


class _Scen7Reader(_EmisInReader):
    pass


class _NonStandardEmisInReader(_InputReader):
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
            pos_block = self._stream.tell()
            region = self._stream.readline().strip()
            try:
                variables = _convert_magicc6_to_magicc7_variables(
                    self._read_data_header_line(self._stream, "YEARS")
                )
            except IndexError:  # tried to get variables from empty string
                break
            except AssertionError:  # tried to get variables from a notes line
                break

            variables = [v + "_EMIS" for v in variables]

            try:
                pos_units = self._stream.tell()
                units = self._read_data_header_line(self._stream, "Yrs")
            except AssertionError:
                # for SRES SCEN files
                self._stream.seek(pos_units)
                units = self._read_data_header_line(self._stream, "YEARS")

            todos = ["SET"] * len(variables)
            regions = [region] * len(variables)

            region_block = StringIO()
            for i in range(no_years):
                region_block.write(self._stream.readline())
            region_block.seek(0)

            region_df = pd.read_csv(
                region_block,
                skip_blank_lines=True,
                delim_whitespace=True,
                header=None,
                index_col=0,
            )
            region_df.index.name = "YEAR"
            region_df.columns = pd.MultiIndex.from_arrays(
                [variables, todos, units, regions],
                names=("VARIABLE", "TODO", "UNITS", "REGION"),
            )

            try:
                df = df.join(region_df)
            except NameError:
                df = region_df

        self._stream.seek(pos_block)

        return df

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

        # now fix labelling, have to copy index :()
        variables = df.columns.get_level_values("VARIABLE").tolist()
        variables = _convert_magicc6_to_magicc7_variables(variables)
        todos = ["SET"] * len(variables)

        concs = False
        emms = False
        if "unit" in metadata:
            if metadata["unit"] == "ppt":
                concs = True
            elif metadata["unit"] == "metric tons":
                emms = True
            else:
                error_msg = "I do not recognise the unit, {}, in file{}".format(
                    metadata["unit"], self.filename
                )
                raise ValueError(error_msg)
        else:
            # just have to assume global emissions in tons
            emms = True

        if concs:
            unit = "ppt"
            region = "GLOBAL"
            variables = [v + "_CONC" for v in variables]
        elif emms:
            unit = "t"
            region = "WORLD"
            variables = [v + "_EMIS" for v in variables]

        units = [unit] * len(variables)
        regions = [region] * len(variables)

        df.columns = pd.MultiIndex.from_arrays(
            [variables, todos, units, regions],
            names=("VARIABLE", "TODO", "UNITS", "REGION"),
        )

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
        df.index.name = "YEAR"
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


def _convert_magicc6_to_magicc7_variables(variables, inverse=False):
    # we generate the mapping dynamically, the first name in the list
    # is the one which will be used for inverse mappings i.e. HFC4310 from
    # MAGICC7 will be mapped back to HFC43-10, not HFC-43-10
    magicc6_vars = [
        "FossilCO2",
        "OtherCO2",
        "SOx",
        "NOx",
        "HFC43-10",
        "HFC-43-10",
        "HFC134a",
        "HFC143a",
        "HFC227ea",
        "HFC245fa",
        "CFC-11",
        "CFC-12",
        "CFC-113",
        "CFC-114",
        "CFC-115",
        "CCl4",
        "CH3CCl3",
        "HCFC-22",
        "HFC-23",
        "HFC-32",
        "HFC-125",
        "HFC-134a",
        "HFC-143a",
        "HCFC-141b",
        "HCFC-142b",
        "HFC-227ea",
        "HFC-245ca",
        "Halon 1211",
        "Halon 1202",
        "Halon 1301",
        "Halon 2402",
        "Halon1211",
        "Halon1202",
        "Halon1301",
        "Halon2402",
        "CH3Br",
        "CH3Cl",
    ]

    # special case replacements
    special_case_replacements = {
        "FossilCO2": "CO2I",
        "OtherCO2": "CO2B",
        "HFC-245ca": "HFC245FA",  # need to check with Malte if this is right...
    }
    replacements = {}
    for m6v in magicc6_vars:
        if m6v in special_case_replacements:
            replacements[m6v] = special_case_replacements[m6v]
        else:
            m7v = m6v.replace("-", "").replace(" ", "").upper()
            # i.e. if we've already got a value for the inverse, we don't # want to overwrite
            if (m7v in replacements.values()) and inverse:
                continue
            replacements[m6v] = m7v

    if inverse:
        replacements = {v: k for k, v in replacements.items()}

    variables_return = deepcopy(variables)
    for old, new in replacements.items():
        if isinstance(variables_return, list):
            variables_return = [v.replace(old, new) for v in variables_return]
        else:
            variables_return = variables_return.replace(old, new)

    return variables_return


def _convert_magicc7_to_magicc6_variables(variables):
    return _convert_magicc6_to_magicc7_variables(variables, inverse=True)


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

    dattype = dattype_regionmode_regions[dattype_flag][region_dattype_row].iloc[0]
    regionmode = dattype_regionmode_regions[regionmode_flag][region_dattype_row].iloc[0]

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
    region_order = dattype_regionmode_regions["Regions"][region_dattype_row].iloc[0]

    return region_order


def _get_dattype_regionmode_regions_row(regions, scen7=False):
    regions_unique = set(regions)

    def find_region(x):
        return set(x) == regions_unique

    region_rows = dattype_regionmode_regions["Regions"].apply(find_region)

    # TODO: move this to a constants module or something
    dattype_flag = "THISFILE_DATTYPE"
    scen7_rows = dattype_regionmode_regions[dattype_flag] == "SCEN7"
    dattype_rows = scen7_rows if scen7 else ~scen7_rows

    region_dattype_row = region_rows & dattype_rows
    assert sum(region_dattype_row) == 1

    return region_dattype_row


class _InputWriter(object):
    # need this for the _get_initial_nml_and_data_block routine as SCEN7
    # files have a special, contradictory set of region flags
    # would be nice to be able to remove in future
    _scen_7 = False
    _newline_char = "\n"
    _variable_header_row_name = "VARIABLE"

    def write(self, magicc_input, filename, filepath=None):
        """
        Write a MAGICC input file from df and metadata

        # Arguments
        magicc_input (MAGICCData): a MAGICCData object which holds the data
            to write
        filename (str): name of file to write to
        filepath (str): path in which to write file. If not provided,
           the file will be written in the current directory (TODO: check this is true...)
        """
        self.minput = magicc_input

        if filepath is not None:
            file_to_write = join(filepath, filename)
        else:
            file_to_write = filename

        output = StringIO()

        output = self._write_header(output)
        output = self._write_namelist(output)
        output = self._write_datablock(output)

        with open(
            file_to_write, "w", encoding="utf-8", newline=self._newline_char
        ) as output_file:
            output.seek(0)
            copyfileobj(output, output_file)

    def _write_header(self, output):
        output.write(self._get_header())
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

        units_unique = list(set(self._get_df_header_row("UNITS")))
        nml["THISFILE_SPECIFICATIONS"]["THISFILE_UNITS"] = (
            units_unique[0] if len(units_unique) == 1 else "MISC"
        )

        nml["THISFILE_SPECIFICATIONS"].update(
            get_dattype_regionmode(
                self._get_df_header_row("REGION"), scen7=self._scen_7
            )
        )

        return nml, data_block

    def _get_data_block(self):
        regions = self._get_df_header_row("REGION")
        variables = self._get_df_header_row("VARIABLE")
        units = self._get_df_header_row("UNITS")
        todos = self._get_df_header_row("TODO")

        data_block = self.minput.df.copy()
        # probably not necessary but a sensible check
        assert data_block.columns.names == ["VARIABLE", "TODO", "UNITS", "REGION"]
        data_block.reset_index(inplace=True)
        data_block.columns = [
            [self._variable_header_row_name] + variables,
            ["TODO"] + todos,
            ["UNITS"] + units,
            ["YEARS"] + regions,
        ]

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

        unit = self.minput.df.columns.get_level_values("UNITS").unique()
        assert len(unit) == 1, "Prn file with more than one unit won't work"
        unit = unit[0]
        if unit == "t":
            lines.append("Unit: metric tons")
            other_col_format_str = "{:9.0f}".format
        elif unit == "ppt":
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

        data_block.columns = data_block.columns.get_level_values("VARIABLE")

        old_style_vars = [
            v.replace("_EMIS", "").replace("_CONC", "")
            for v in data_block.columns.get_level_values("VARIABLE")
        ]
        data_block.columns = old_style_vars

        emms_assert_msg = (
            "Prn files must have, and only have, "
            "the following species: ".format(prn_species)
        )
        assert set(data_block.columns) == set(prn_species), emms_assert_msg

        data_block.index.name = "Years"
        data_block.reset_index(inplace=True)

        return data_block


class _ScenWriter(_InputWriter):
    def _write_header(self, output):
        header_lines = []
        header_lines.append("{}".format(len(self.minput.df)))

        variables = self._get_df_header_row("VARIABLE")
        variables = [v.replace("_EMIS", "") for v in variables]
        special_scen_code = get_special_scen_code(
            regions=self._get_df_header_row("REGION"), emissions=variables
        )
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
            self._get_df_header_row("REGION"), scen7=self._scen_7
        )
        # format is vitally important for SCEN files as far as I can tell
        time_col_length = 12
        first_col_format_str = ("{" + ":{}d".format(time_col_length) + "}").format
        other_col_format_str = "{:11.4f}".format

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

        for region in region_order:
            region_block = self.minput[region]
            region_block.columns = region_block.columns.droplevel("TODO")
            region_block.columns = region_block.columns.droplevel("REGION")

            variables = region_block.columns.get_level_values("VARIABLE").tolist()
            variables = _convert_magicc7_to_magicc6_variables(
                [v.replace("_EMIS", "") for v in variables]
            )

            units = region_block.columns.get_level_values("UNITS").tolist()

            assert region_block.columns.names == ["VARIABLE", "UNITS"]
            region_block.reset_index(inplace=True)
            region_block.columns = [["YEARS"] + variables, ["Yrs"] + units]

            # I have no idea why these spaces are necessary at the moment, something wrong with pandas...?
            pd_pad = " " * (
                time_col_length - len(self.minput.df.columns.get_level_values(0)[0]) - 2
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
    number. The first digit tells MAGICC how many regions data is being
    provided for. The second digit tells MAGICC which gases are in the
    SCEN file.

    We call this second digit the 'SCEN emms code'. Hence the variable
    ``scen_emms_code_1`` defines the gases which are expected when the
    'SCEN emms code' is 1. Similarly, ``scen_emms_code_0`` defines the gases
    which are expected when the 'SCEN emms code' is 0.

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
    if set(scen_emms_code_0) == set(emissions):
        emms_code = 0
    elif set(scen_emms_code_1) == set(emissions):
        emms_code = 1
    else:
        msg = "Could not determine scen special code for emissions {}".format(emissions)
        raise ValueError(msg)

    if set(regions) == set(["WORLD"]):
        return 10 + emms_code
    elif set(regions) == set(["WORLD", "OECD90", "REF", "ASIA", "ALM"]):
        return 20 + emms_code
    elif set(regions) == set(["WORLD", "R5OECD", "R5REF", "R5ASIA", "R5MAF", "R5LAM"]):
        return 30 + emms_code
    elif set(regions) == set(
        ["WORLD", "R5OECD", "R5REF", "R5ASIA", "R5MAF", "R5LAM", "BUNKERS"]
    ):
        return 40 + emms_code

    msg = "Could not determine scen special code for regions {}".format(regions)
    raise ValueError(msg)


def _get_subdf_from_df_for_key(df, key):
    for colname in df.columns.names:
        try:
            return df.xs(key, level=colname, axis=1, drop_level=False)
        except KeyError:
            continue
    try:
        return df.loc[[key]]
    except KeyError:
        msg = "{} is not in the column headers or the index".format(key)
        raise KeyError(msg)


def _get_subdf_from_df_for_keys(df, keys):
    df_out = df.copy()
    if isinstance(keys, str):
        keys = [keys]
    try:
        for key in keys:
            df_out = _get_subdf_from_df_for_key(df_out, key)
    except TypeError:
        df_out = _get_subdf_from_df_for_key(df_out, keys)
    return df_out


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
    filename : str
        Optional file name, including extension, for the target
        file, i.e. 'HISTRCP_CO2I_EMIS.IN'. The file is not read until the search
        directory is provided in ``read``. This allows for MAGICCData files to be
        lazy-loaded once the appropriate MAGICC run directory is known.
    """

    def __init__(self, filename=None):
        """
        Initialise a MAGICCData object.
        """
        self.df = None
        self.metadata = {}
        self.filename = filename

    def __getitem__(self, item):
        """
        Allow for simplified indexing.

        TODO: double check or delete below
        >>> inpt = MAGICCData('HISTRCP_CO2_CONC.IN')
        >>> inpt.read('./')
        >>> assert (inpt['CO2', 'GLOBAL'] == inpt.df['CO2', :, :, 'GLOBAL']).all()
        """
        if not self.is_loaded:
            self._raise_not_loaded_error()
        return _get_subdf_from_df_for_keys(self.df, item)

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
        return self.df is not None

    def read(self, filepath=None, filename=None):
        """
        Read an input file from disk.

        Parameters
        ----------
        filepath : str
            The directory to read the file from. This is often the
            run directory for a magicc instance. If None is passed,
            the run directory for the version of MAGICC6 included in pymagicc
            is used.
        filename : str
            The filename to read. Overrides any existing values.
            If None is passed, the filename used to initialise the MAGICCData
            instance is used.
        """
        if filepath is None:
            filepath = MAGICC6().original_dir
        if filename is not None:
            self.filename = filename
        assert self.filename is not None

        file_to_read = join(filepath, self.filename)
        _check_file_exists(file_to_read)

        reader = self.determine_tool(file_to_read, "reader")(file_to_read)
        self.metadata, self.df = reader.read()

    def write(self, filename_to_write, filepath=None):
        """
        Write an input file from disk.

        Parameters
        ----------
        filename_to_write : str
            The name of the file to write. The filename
            is critically important as it tells MAGICC what kind of file to
            write.
        filepath_to_write : str
            The directory to write the file to. This is
            often the run directory for a magicc instance. If None is passed,
            the current working directory is used.
        """
        writer = self.determine_tool(filename_to_write, "writer")()
        writer.write(self, filename_to_write, filepath)

    def determine_tool(self, filename, tool_to_get):
        """
        Determine the tool to use for reading/writing.

        The function uses an internally defined set of mappings between filenames,
        regular expresions and readers/writers to work out which tool to use
        for a given task, given the filename.

        It is intended for internal use only, but is public because of its
        importance to the input/output of pymagicc.

        If it fails, it will give clear error messages about why and what the
        available regular expressions are.

        .. code:: python

            >>> mdata = MAGICCData()
            >>> mdata.read(MAGICC7_DIR, HISTRCP_CO2I_EMIS.txt)
            ValueError: Couldn't find appropriate writer for HISTRCP_CO2I_EMIS.txt.
            The file must be one of the following types and the filename must match its corresponding regular expression:
            SCEN: ^.*\\.SCEN$
            SCEN7: ^.*\\.SCEN7$
            prn: ^.*\\.prn$

        Parameters
        ----------
        filename : str
            Name of the file to read/write, including extension
        tool_to_get : str
            The tool to get, valid options are "reader", "writer".
            Invalid values will throw a KeyError.
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
            # "InverseEmisOut": {"regexp": r"^INVERSEEMIS\_.*\.OUT$", "reader": _Scen7Reader, "writer": _Scen7Writer},
        }

        fbase = basename(filename)
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

        if (filename.endswith(".CFG")) and (tool_to_get == "reader"):
            error_msg = (
                "MAGCCInput cannot read .CFG files like {}, please use "
                "pymagicc.io.read_cfg_file".format(filename)
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
                "of the following types and the filename must match its "
                "corresponding regular "
                "expression:\n{}".format(tool_to_get, fbase, regexp_list_str)
            )

        raise ValueError(error_msg)


def _check_file_exists(file_to_read):
    if not exists(file_to_read):
        raise ValueError("Cannot find {}".format(file_to_read))


def read_cfg_file(fullfilename):
    _check_file_exists(fullfilename)
    return f90nml.read(fullfilename)
