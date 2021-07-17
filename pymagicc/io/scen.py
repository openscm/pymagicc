import warnings

import pandas as pd
from six import StringIO

from pymagicc.definitions import (
    PART_OF_SCENFILE_WITH_EMISSIONS_CODE_0,
    PART_OF_SCENFILE_WITH_EMISSIONS_CODE_1,
    convert_magicc6_to_magicc7_variables,
    convert_magicc7_to_openscm_variables,
    convert_magicc_to_openscm_regions,
    convert_pint_to_fortran_safe_units,
)

from .base import _EmisInReader, _Writer
from .utils import _strip_emis_variables, get_region_order


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
                variables = self._read_data_header_line(
                    self._stream, ["Years", "Year", "YEARS", "YEAR"]
                )
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
        variables = _strip_emis_variables(variables)

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
        variables = _strip_emis_variables(variables)

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
                levels=_strip_emis_variables(variables), level="variable",
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
