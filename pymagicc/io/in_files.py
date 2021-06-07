import re

from pymagicc.definitions import (
    convert_magicc6_to_magicc7_variables,
    convert_magicc7_to_openscm_variables,
)

from .base import _EmisInReader, _FourBoxReader, _Writer
from .utils import _strip_emis_variables


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
        return _strip_emis_variables(hr)
