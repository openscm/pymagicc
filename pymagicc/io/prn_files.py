import re

import numpy as np
import pandas as pd
from six import StringIO

from ..definitions import (
    PART_OF_PRNFILE,
    convert_magicc6_to_magicc7_variables,
    convert_magicc7_to_openscm_variables,
    convert_magicc_to_openscm_regions,
)
from .base import _Writer
from .scen import _NonStandardEmisInReader


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
        data_block = self._get_timeseries_no_nans()
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
