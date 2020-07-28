import re
import warnings

from pymagicc.io.in_files import _HistEmisInWriter, _StandardEmisInReader


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
