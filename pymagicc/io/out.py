import re

from pymagicc.definitions import (
    convert_magicc6_to_magicc7_variables,
    convert_magicc7_to_openscm_variables,
)

from .base import _FourBoxReader, _Reader
from .in_files import _EmisInReader


class _OutReader(_FourBoxReader):
    _regexp_capture_variable = re.compile(r"DAT\_(\w*)\.OUT$")
    _default_todo_fill_value = "not_relevant"

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
    _default_todo_fill_value = "not_relevant"

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
