import warnings
from datetime import datetime

from six import StringIO

from pymagicc.definitions import (
    convert_magicc6_to_magicc7_variables,
    convert_magicc7_to_openscm_variables,
    convert_pint_to_fortran_safe_units,
)

from .base import _EmisInReader, _Reader, _Writer


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
            "the `ScmRun` format instead (just call `.to_csv()`). Our `.DAT` "
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
