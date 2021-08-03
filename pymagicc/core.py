import shutil
import subprocess  # nosec # have to use subprocess
import warnings
from collections import Counter
from copy import deepcopy
from os import listdir, makedirs
from os.path import abspath, basename, dirname, exists, isfile, join
from subprocess import PIPE  # nosec # have to use subprocess
from tempfile import mkdtemp

import f90nml
import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta
from openscm_units import unit_registry
from scmdata import run_append

from .config import _wine_installed, config
from .errors import InvalidTemporalResError, NoReaderWriterError
from .io import MAGICCData, read_cfg_file
from .io.utils import _get_openscm_var_from_filepath
from .scenarios import zero_emissions
from .utils import get_date_time_string

IS_WINDOWS = config["is_windows"]


class WineNotInstalledError(Exception):
    """Exception raised if wine is not installed but is required"""


def _copy_files(source, target, recursive=False):
    """
    Copy all the files in source directory to target.

    If ``recursive``, include subdirectories, otherwise ignores subdirectories.
    """
    if recursive:
        shutil.copytree(source, target)

        return

    source_files = listdir(source)

    if not exists(target):
        makedirs(target)

    for filename in source_files:
        full_filename = join(source, filename)
        if isfile(full_filename):
            shutil.copy(full_filename, target)


def _clean_value(v):
    if isinstance(v, str):
        return v.strip()
    elif isinstance(v, list):
        if isinstance(v[0], str):
            return [i.replace("\0", "").strip().replace("\n", "") for i in v]
    return v


class MAGICCBase(object):
    """
    Provides access to the MAGICC binary and configuration.

    To enable multiple MAGICC 'setups' to be configured independently,
    the MAGICC directory containing the input files, configuration
    and binary is copied to a new folder. The configuration in this
    MAGICC copy can then be edited without impacting other instances or your
    original MAGICC distribution.

    A ``MAGICC`` instance first has to be setup by calling
    ``create_copy``. If many model runs are being performed this step only has
    to be performed once. The ``run`` method can then be called many times
    without re-copying the files each time. Between each call to ``run``, the
    configuration files can be updated to perform runs with different
    configurations.

    Parameters
    ----------
    root_dir : str
        If ``root_dir`` is supplied, an existing MAGICC 'setup' is
        used.
    """

    version = None
    _scen_file_name = "SCENARIO.SCEN7"

    def __init__(self, root_dir=None, strict=True):
        """
        Initialise

        Parameters
        ----------
        root_dir : str
            Root directory of the MAGICC package. If ``None``, a temporary
            copy of MAGICC is made based on the result of `
            `self.get_exectuable()``.
        strict: bool
            If True, enforce the configuration checks, otherwise a warning
            is raised if any invalid configuration is found and the run is
            continued. Setting ``strict=False`` is only recommended for
            experienced users of MAGICC.
        """
        self.root_dir = root_dir
        self.config = None
        self.executable = self.get_executable()
        self.strict = strict

        if root_dir is not None:
            self.is_temp = False
        else:
            # Create a temp directory
            self.is_temp = True

    def __enter__(self):
        if self.is_temp and self.run_dir is None:
            self.create_copy()
        return self

    def __exit__(self, *args, **kwargs):
        self.remove_temp_copy()

    def create_copy(self):
        """
        Initialises a temporary directory structure and copy of MAGICC
        configuration files and binary.

        The root folder and ``bin`` folders are copied (not recursively). The
        ``run`` folder is copied recursively.
        """
        if self.executable is None or not isfile(self.executable):
            raise FileNotFoundError(
                "Could not find MAGICC{} executable: {}".format(
                    self.version, self.executable
                )
            )
        if self.is_temp:
            if self.root_dir is not None:
                raise AssertionError(
                    "A temp copy for this instance has already been created"
                )

            self.root_dir = mkdtemp(prefix="pymagicc-")

        if exists(self.run_dir):
            raise Exception("A copy of MAGICC has already been created.")

        if not exists(self.root_dir):
            makedirs(self.root_dir)

        exec_dir = basename(self.original_dir)

        # Copy a subset of folders from the MAGICC `original_dir`
        # Also copy anything which is in the root of the MAGICC distribution
        # Assumes that the MAGICC binary is in a folder one level below the root
        # of the MAGICC distribution. i.e. /run/magicc.exe or /bin/magicc
        dirs_to_copy = [".", "bin"]
        dirs_to_copy_recursive = ["run"]
        # Check that the executable is in a valid sub directory
        if exec_dir not in dirs_to_copy + dirs_to_copy_recursive:
            raise AssertionError("binary must be in bin/ or run/ directory")

        for d in dirs_to_copy + dirs_to_copy_recursive:
            source_dir = abspath(join(self.original_dir, "..", d))
            if exists(source_dir):
                _copy_files(
                    source_dir,
                    join(self.root_dir, d),
                    recursive=d in dirs_to_copy_recursive,
                )

        # Create an empty out dir
        # MAGICC assumes that the 'out' directory already exists
        makedirs(join(self.root_dir, "out"))

        # Create basic configuration files so magicc can run
        self.set_years()
        self.set_config()

    @property
    def binary_name(self):
        """
        Name of the MAGICC binary file

        Returns
        -------
        str
            Name of the binary file
        """
        return basename(self.executable)

    @property
    def original_dir(self):
        """
        Directory of the MAGICC package.

        This is the directory which contains the ``run`` and ``out`` folders.

        Returns
        -------
        str
            Path of the MAGICC package
        """
        return dirname(self.executable)

    @property
    def run_dir(self):
        """
        Run directory of the MAGICC package.

        This path always ends in ``run``.

        Returns
        -------
        str
            Path of the run directory
        """
        if self.root_dir is None:
            return None
        return join(self.root_dir, "run")

    @property
    def out_dir(self):
        """
        Output directory of the MAGICC package.

        This path always ends in ``out``.

        Returns
        -------
        str
            Path of the output directory
        """
        if self.root_dir is None:
            return None
        return join(self.root_dir, "out")

    @property
    def default_config(self):
        """
        Default configuration for a run

        Returns
        -------
        :obj:`f90nml.Namelist`
            Namelist object containing the default configuration
        """
        base = f90nml.read(join(self.run_dir, "MAGCFG_DEFAULTALL.CFG"))
        user = f90nml.read(join(self.run_dir, "MAGCFG_USER.CFG"))
        self._default_config = deepcopy(base)

        def _deep_update(b, o):
            for k, v in o.items():
                if isinstance(v, dict):
                    _deep_update(b[k], v)
                else:
                    b.update(o)

        _deep_update(self._default_config, user)

        return self._default_config

    def run(self, scenario=None, only=None, debug=False, **kwargs):
        """
        Run MAGICC and parse the output.

        As a reminder, putting ``out_parameters=1`` will cause MAGICC to write out its
        parameters into ``out/PARAMETERS.OUT`` and they will then be read into
        ``output.metadata["parameters"]`` where ``output`` is the returned object.

        Any logged output from running magicc will be in``output.metadata["stderr"]``.
        For MAGICC7 and above, The level of logging can be controlled with the
        ``debug`` argument.

        Any subannual files output by MAGICC will be ignored by this function. These
        files can be read in manually using :class:`pymagicc.io.MAGICCData` directly.

        Parameters
        ----------
        scenario : :obj:`pymagicc.io.MAGICCData`
            Scenario to run. If None MAGICC will simply run with whatever config has
            already been set.

        only : list of str
            If not None, only extract variables in this list.

        debug: {True, False, "verbose"}
            If true, MAGICC will run in debug mode with the maximum amount of logging.
            If "verbose", MAGICC will be run in verbose mode.

        kwargs
            Other config values to pass to MAGICC for the run

        Returns
        -------
        :obj:`pymagicc.io.MAGICCData`
            MAGICCData object containing that data in its ``df`` attribute and
            metadata and parameters (depending on the value of ``include_parameters``)
            in its ``metadata`` attribute.

        Raises
        ------
        ValueError
            If no output is found which matches the list specified in ``only``.

        subprocess.CalledProcessError
            If MAGICC fails to run. Check the 'stderr' key of the result's `metadata`
            attribute to inspect the results output from MAGICC.

        ValueError
            The user attempts to use ``debug`` with MAGICC6
        """
        if not exists(self.root_dir):
            raise FileNotFoundError(self.root_dir)

        if self.executable is None:
            raise ValueError(
                "MAGICC executable not found, try setting an environment variable `MAGICC_EXECUTABLE_{}=/path/to/binary`".format(
                    self.version
                )
            )

        if scenario is not None:
            kwargs = self.set_emission_scenario_setup(scenario, kwargs)

        yr_config = {}
        if "startyear" in kwargs:
            yr_config["startyear"] = kwargs.pop("startyear")
        if "endyear" in kwargs:
            yr_config["endyear"] = kwargs.pop("endyear")
        if yr_config:
            self.set_years(**yr_config)

        # should be able to do some other nice metadata stuff re how magicc was run
        # etc. here
        kwargs.setdefault("rundate", get_date_time_string())

        self.update_config(**kwargs)

        self.check_config()

        exec_dir = basename(self.original_dir)
        command = [join(self.root_dir, exec_dir, self.binary_name)]
        if self.version >= 7:
            if debug == "verbose":
                command.append("--verbose")
            elif debug:
                command.append("--debug")
        elif debug:
            raise ValueError("MAGICC6 has no debug capability")

        if not IS_WINDOWS and self.binary_name.endswith(".exe"):  # pragma: no cover
            if not _wine_installed:
                raise WineNotInstalledError(
                    "Wine is not installed but is required to run `.exe` binaries"
                )
            command.insert(0, "wine")

        try:
            res = subprocess.run(  # nosec # on Windows shell=True is required
                command,
                check=True,
                # thank you https://stackoverflow.com/a/53209196 for Python 3.6 hack
                stdout=PIPE,
                stderr=PIPE,
                cwd=self.run_dir,
                shell=IS_WINDOWS,
            )
        except subprocess.CalledProcessError as exc:
            print("stderr:\n{}".format(exc.stderr.decode()))
            raise exc

        outfiles = self._get_output_filenames()
        read_cols = {"climate_model": ["MAGICC{}".format(self.version)]}
        if scenario is not None:
            read_cols["model"] = scenario["model"].unique().tolist()
            read_cols["scenario"] = scenario["scenario"].unique().tolist()
        else:
            read_cols.setdefault("model", ["unspecified"])
            read_cols.setdefault("scenario", ["unspecified"])

        mdata = []
        for filepath in outfiles:
            if filepath.startswith("DAT_VOLCANIC_RF.") or "SUBANN" in filepath:
                warnings.warn(
                    "Not reading file: {}. Monthly data are not read in automatically by `run`. "
                    "Use `MAGICCData` instead.".format(filepath)
                )
                continue
            try:
                openscm_var = _get_openscm_var_from_filepath(filepath)
                if only is None or openscm_var in only:
                    tempdata = MAGICCData(
                        join(self.out_dir, filepath), columns=deepcopy(read_cols)
                    )
                    mdata.append(tempdata)

            except (NoReaderWriterError, InvalidTemporalResError):
                # TODO: something like warnings.warn("Could not read {}".format(filepath))
                continue

        if not mdata and only is not None:
            raise ValueError("No output found for only={}".format(only))

        if not mdata:
            if self.strict:
                raise ValueError("No output found. Check configuration")
            else:
                # No data was loaded return an empty MAGICCData object
                mdata = MAGICCData(
                    data={},
                    columns={
                        "model": [],
                        "unit": [],
                        "variable": [],
                        "region": [],
                        "scenario": [],
                    },
                )
        else:
            mdata = run_append(mdata)

        try:
            run_paras = self.read_parameters()
            self.config = run_paras
            mdata.metadata["parameters"] = run_paras
        except FileNotFoundError:
            pass

        mdata.metadata["stderr"] = res.stderr.decode("ascii")
        levels_to_warn = ["WARNING", "ERROR", "FATAL"]
        for level in levels_to_warn:
            if "<{}>".format(level) in mdata.metadata["stderr"]:
                warnings.warn(
                    "magicc logged a {} message. Check the 'stderr' key of the "
                    "result's `metadata` attribute.".format(level)
                )

        return mdata

    def _get_output_filenames(self):
        outfiles = [f for f in listdir(self.out_dir) if f != "PARAMETERS.OUT"]

        bin_out = [
            f.split(".")[0]
            for f in outfiles
            if f.startswith("DAT_") and f.endswith(".BINOUT")
        ]

        extras = []
        for f in outfiles:
            var_name, ext = f.split(".")
            if ext != "BINOUT" and var_name not in bin_out:
                extras.append(f)

        return [f + ".BINOUT" for f in bin_out] + extras

    def _check_failed(self, msg):
        if self.strict:
            raise ValueError(msg)
        else:
            warnings.warn(msg)

    def check_config(self):
        """Check that our MAGICC ``.CFG`` files are set to safely work with PYMAGICC

        For further detail about why this is required, please see :ref:`MAGICC flags`.

        Raises
        ------
        ValueError
            If we are not certain that the config written by PYMAGICC will overwrite
            all other config i.e. that there will be no unexpected behaviour. A
            ValueError will also be raised if the user tries to use more than one
            scenario file.
        """
        cfg_error_msg = (
            "PYMAGICC is not the only tuning model that will be used by "
            "`MAGCFG_USER.CFG`: your run is likely to fail/do odd things"
        )
        emisscen_error_msg = (
            "You have more than one `FILE_EMISSCEN_X` flag set. Using more than "
            "one emissions scenario is hard to debug and unnecessary with "
            "Pymagicc's Dataframe scenario input. Please combine all your "
            "scenarios into one Dataframe with Pymagicc and Pandas, then feed "
            "this single Dataframe into Pymagicc's run API."
        )

        nml_to_check = "nml_allcfgs"
        usr_cfg = read_cfg_file(join(self.run_dir, "MAGCFG_USER.CFG"))
        for k in usr_cfg[nml_to_check]:
            if k.startswith("file_tuningmodel"):
                first_tuningmodel = k in ["file_tuningmodel", "file_tuningmodel_1"]
                if first_tuningmodel:
                    if usr_cfg[nml_to_check][k] != "PYMAGICC":
                        self._check_failed(cfg_error_msg)
                elif usr_cfg[nml_to_check][k] not in ["USER", ""]:
                    self._check_failed(cfg_error_msg)

            elif k.startswith("file_emisscen_"):
                if usr_cfg[nml_to_check][k] not in ["NONE", ""]:
                    self._check_failed(emisscen_error_msg)

        self._check_config()

    def write(self, mdata, name):
        """Write an input file to disk

        Parameters
        ----------
        mdata : :obj:`pymagicc.io.MAGICCData`
            A MAGICCData instance with the data to write

        name : str
            The name of the file to write. The file will be written to the MAGICC
            instance's run directory i.e. ``self.run_dir``
        """
        mdata.write(join(self.run_dir, name), self.version)

    def read_parameters(self):
        """
        Read a parameters.out file

        Returns
        -------
        dict
            A dictionary containing all the configuration used by MAGICC
        """
        param_fname = join(self.out_dir, "PARAMETERS.OUT")

        if not exists(param_fname):
            raise FileNotFoundError("No PARAMETERS.OUT found")

        with open(param_fname) as nml_file:
            parameters = dict(f90nml.read(nml_file))
            for group in ["nml_years", "nml_allcfgs", "nml_outputcfgs"]:
                parameters[group] = dict(parameters[group])
                for k, v in parameters[group].items():
                    parameters[group][k] = _clean_value(v)
                parameters[group.replace("nml_", "")] = parameters.pop(group)
            self.config = parameters
        return parameters

    def remove_temp_copy(self):
        """
        Removes a temporary copy of the MAGICC version shipped with Pymagicc.
        """
        if self.is_temp and self.root_dir is not None:
            shutil.rmtree(self.root_dir)
            self.root_dir = None

    def set_config(
        self,
        filename="MAGTUNE_PYMAGICC.CFG",
        top_level_key="nml_allcfgs",
        conflict="warn",
        **kwargs,
    ):
        """
        Create a configuration file for MAGICC.

        Writes a fortran namelist in run_dir.

        Parameters
        ----------
        filename : str
            Name of configuration file to write

        top_level_key : str
            Name of namelist to be written in the
            configuration file

        conflict : {'warn', 'ignore'}
            If 'warn', when a flag needs to be replaced by a different name (because,
            for example, the flag name changed between MAGICC versions), a warning is
            raised. If 'ignore', no warning is raised when a replacement is required.

        kwargs
            Other parameters to pass to the configuration file. No
            validation on the parameters is performed.

        Returns
        -------
        dict
            The contents of the namelist which was written to file

        Warning
        -------
            If a key is renamed, a warning is raised

        Raises
        ------
        ValueError
            An invalid value for ``conflict`` is supplied
        """
        kwargs = self._check_and_format_config(kwargs)

        fname = join(self.run_dir, filename)
        conf = {top_level_key: kwargs}
        conf = self._fix_legacy_keys(conf, conflict=conflict)
        f90nml.write(conf, fname, force=True)

        return conf

    def update_config(
        self,
        filename="MAGTUNE_PYMAGICC.CFG",
        top_level_key="nml_allcfgs",
        conflict="warn",
        **kwargs,
    ):
        """Updates a configuration file for MAGICC

        Updates the contents of a fortran namelist in the run directory,
        creating a new namelist if none exists.

        Parameters
        ----------
        filename : str
            Name of configuration file to write

        top_level_key : str
            Name of namelist to be written in the
            configuration file

        conflict : {'warn', 'ignore'}
            If 'warn', when a flag needs to be replaced by a different name (because,
            for example, the flag name changed between MAGICC versions), a warning is
            raised. If 'ignore', no warning is raised when a replacement is required.

        kwargs
            Other parameters to pass to the configuration file. No
            validation on the parameters is performed.

        Returns
        -------
        dict
            The contents of the namelist which was written to file

        Warning
        -------
            If a key is renamed, a warning is raised

        Raises
        ------
        ValueError
            An invalid value for ``conflict`` is supplied
        """
        kwargs = self._check_and_format_config(kwargs)
        fname = join(self.run_dir, filename)

        if exists(fname):
            conf = f90nml.read(fname)
        else:
            conf = {top_level_key: {}}

        conf[top_level_key].update(kwargs)
        conf = self._fix_legacy_keys(conf, conflict=conflict)
        f90nml.write(conf, fname, force=True)

        return conf

    def _fix_legacy_keys(self, conf, conflict="warn"):
        """
        Go through config and fix any keys which are misnamed.

        For example, fix any keys which have been renamed between MAGICC versions to
        match the new names.

        Parameters
        ----------
        conf :obj:`f90nml.Namelist`
            Configuration to check

        conflict : {'warn', 'ignore'}
            If 'warn', when a conflict is found, a warning is raised. If 'ignore', no
            warning is raised when a conflict is found.

        Returns
        -------
        :obj:`f90nml.Namelist`
            Configuration with updated keys

        Warning
        -------
            If a key is renamed, a warning is raised

        Raises
        ------
        ValueError
            An invalid value for ``conflict`` is supplied
        """
        valid_conflicts = ["warn", "ignore"]
        if conflict not in valid_conflicts:
            raise ValueError("`conflict` must be one of: {}".format(valid_conflicts))

        cfg_key = "nml_allcfgs"
        if cfg_key not in conf:
            return conf

        new_conf = deepcopy(conf)
        for wrong_key, right_key in self._config_renamings.items():
            if wrong_key in new_conf[cfg_key]:
                new_conf[cfg_key][right_key] = new_conf[cfg_key].pop(wrong_key)
                if conflict == "warn":
                    warnings.warn(
                        "Altering config flag {} to {}".format(wrong_key, right_key)
                    )

        return new_conf

    def set_zero_config(self):
        """Set config such that radiative forcing and temperature output will be zero

        This method is intended as a convenience only, it does not handle everything in
        an obvious way. Adjusting the parameter settings still requires great care and
        may behave unepexctedly.
        """
        # zero_emissions is imported from scenarios module
        # TODO: setup MAGICC6 so it puts extra variables in right place and hence
        # warning about ignoring some data disappears
        zero_emissions.write(join(self.run_dir, self._scen_file_name), self.version)

        time = zero_emissions.filter(variable="Emissions|CH4", region="World")[
            "time"
        ].values
        no_timesteps = len(time)
        # value doesn't actually matter as calculations are done from difference but
        # chose sensible value nonetheless
        co2_conc_pi = 722
        co2_conc = co2_conc_pi * np.ones(no_timesteps)
        co2_conc_df = pd.DataFrame(
            {
                "time": time,
                "scenario": "idealised",
                "model": "unspecified",
                "climate_model": "unspecified",
                "variable": "Atmospheric Concentrations|CO2",
                "unit": "ppm",
                "todo": "SET",
                "region": "World",
                "value": co2_conc,
            }
        )
        co2_conc_writer = MAGICCData(co2_conc_df)
        co2_conc_filename = "HIST_CONSTANT_CO2_CONC.IN"
        co2_conc_writer.metadata = {
            "header": "Constant pre-industrial CO2 concentrations"
        }
        co2_conc_writer.write(join(self.run_dir, co2_conc_filename), self.version)

        ch4_conc_pi = 722
        ch4_conc = ch4_conc_pi * np.ones(no_timesteps)
        ch4_conc_df = pd.DataFrame(
            {
                "time": time,
                "scenario": "idealised",
                "model": "unspecified",
                "climate_model": "unspecified",
                "variable": "Atmospheric Concentrations|CH4",
                "unit": "ppb",
                "todo": "SET",
                "region": "World",
                "value": ch4_conc,
            }
        )
        ch4_conc_writer = MAGICCData(ch4_conc_df)
        ch4_conc_filename = "HIST_CONSTANT_CH4_CONC.IN"
        ch4_conc_writer.metadata = {
            "header": "Constant pre-industrial CH4 concentrations"
        }
        ch4_conc_writer.write(join(self.run_dir, ch4_conc_filename), self.version)

        fgas_conc_pi = 0
        fgas_conc = fgas_conc_pi * np.ones(no_timesteps)

        varname = "FGAS_CONC"
        fgas_conc_df = pd.DataFrame(
            {
                "time": time,
                "scenario": "idealised",
                "model": "unspecified",
                "climate_model": "unspecified",
                "variable": varname,
                "unit": "ppt",
                "todo": "SET",
                "region": "World",
                "value": fgas_conc,
            }
        )
        fgas_conc_writer = MAGICCData(fgas_conc_df)
        fgas_conc_filename = "HIST_ZERO_{}.IN".format(varname)
        fgas_conc_writer.metadata = {"header": "Zero concentrations"}
        fgas_conc_writer.write(join(self.run_dir, fgas_conc_filename), self.version)

        def_config = self.default_config
        tmp_nml = f90nml.Namelist({"nml_allcfgs": {"fgas_files_conc": 1}})
        fgas_files_conc_flag = list(
            self._fix_legacy_keys(tmp_nml, conflict="ignore")["nml_allcfgs"].keys()
        )[0]
        fgas_conc_files = [fgas_conc_filename] * len(
            def_config["nml_allcfgs"][fgas_files_conc_flag]
        )

        self.set_config(
            conflict="ignore",
            file_emisscen=self._scen_file_name,
            rf_initialization_method="ZEROSTARTSHIFT",
            rf_total_constantafteryr=10000,
            file_co2i_emis="",
            file_co2b_emis="",
            file_co2_conc=co2_conc_filename,
            co2_switchfromconc2emis_year=10000,
            file_ch4i_emis="",
            file_ch4b_emis="",
            file_ch4n_emis="",
            file_ch4_conc=ch4_conc_filename,
            ch4_switchfromconc2emis_year=10000,
            file_n2oi_emis="",
            file_n2ob_emis="",
            file_n2on_emis="",
            file_n2o_conc="",
            n2o_switchfromconc2emis_year=1750,
            file_noxi_emis="",
            file_noxb_emis="",
            file_noxi_ot="",
            file_noxb_ot="",
            file_noxt_rf="",
            file_soxnb_ot="",
            file_soxi_ot="",
            file_soxt_rf="",
            file_soxi_emis="",
            file_soxb_emis="",
            file_soxn_emis="",
            file_oci_emis="",
            file_ocb_emis="",
            file_oci_ot="",
            file_ocb_ot="",
            file_oci_rf="",
            file_ocb_rf="",
            file_bci_emis="",
            file_bcb_emis="",
            file_bci_ot="",
            file_bcb_ot="",
            file_bci_rf="",
            file_bcb_rf="",
            bcoc_switchfromrf2emis_year=1750,
            file_nh3i_emis="",
            file_nh3b_emis="",
            file_nmvoci_emis="",
            file_nmvocb_emis="",
            file_coi_emis="",
            file_cob_emis="",
            file_mineraldust_rf="",
            file_landuse_rf="",
            file_bcsnow_rf="",
            # rf_fgassum_scale=0,  # this appears to do nothing, hence the next two lines
            fgas_switchfromconc2emis_year=10000,
            rf_mhalosum_scale=0,
            stratoz_o3scale=0,
            rf_volcanic_scale=0,
            rf_solar_scale=0,
            mhalo_switchfromconc2emis_year=1750,
            fgas_files_conc=fgas_conc_files,
        )

    def _check_and_format_config(self, config_dict):
        self._check_for_duplicate_keys(config_dict)

        config_dict = self._convert_out_config_flags_to_integers(config_dict)

        return config_dict

    @staticmethod
    def _check_for_duplicate_keys(config_dict):
        keys_lower = [v.lower() for v in config_dict.keys()]
        counts = Counter(keys_lower)
        if any([v > 1 for v in counts.values()]):
            duplicate_keys = [
                [ck for ck in config_dict.keys() if ck.lower() == k.lower()]
                for k, v in counts.items()
                if v > 1
            ]

            error_msg = (
                "The following configuration keys clash because configs are "
                "case insensitive: {}".format(
                    ", ".join([str(v) for v in duplicate_keys])
                )
            )

            raise ValueError(error_msg)

    @staticmethod
    def _convert_out_config_flags_to_integers(config_dict):
        valid_out_flags = [
            "out_emissions",
            "out_gwpemissions",
            "out_sum_gwpemissions",
            "out_concentrations",
            "out_carboncycle",
            "out_forcing",
            "out_forcing_subannual",
            "out_temperature",
            "out_temperature_subannual",
            "out_sealevel",
            "out_parameters",
            "out_misc",
            "out_lifetimes",
            "out_timeseriesmix",
            "out_rcpdata",
            "out_summaryidx",
            "out_tempoceanlayers",
            "out_oceanarea",
            "out_heatuptake",
            "out_warnings",
            "out_precipinput",
            "out_aogcmtuning",
            "out_ccycletuning",
            "out_observationaltuning",
            "out_keydata_1",
            "out_keydata_2",
            "out_inverseemis",
            "out_surfaceforcing",
            "out_permafrost",
            "out_allowanydynamicvars",
        ]
        for key in valid_out_flags:
            if key in config_dict:
                # MAGICC expects 1 and 0 instead of True/False
                config_dict[key] = 1 if config_dict[key] else 0

        return config_dict

    def set_years(self, startyear=1765, endyear=2100):
        """
        Set the start and end dates of the simulations.

        Parameters
        ----------
        startyear : int
            Start year of the simulation

        endyear : int
            End year of the simulation

        Returns
        -------
        dict
            The contents of the namelist
        """
        # TODO: test altering stepsperyear, I think 1, 2 and 24 should all work
        return self.set_config(
            "MAGCFG_NMLYEARS.CFG",
            "nml_years",
            endyear=endyear,
            startyear=startyear,
            stepsperyear=12,
        )

    def set_output_variables(self, write_ascii=True, write_binary=False, **kwargs):
        """Set the output configuration, minimising output as much as possible

        There are a number of configuration parameters which control which variables
        are written to file and in which format. Limiting the variables that are
        written to file can greatly speed up the running of MAGICC. By default,
        calling this function without specifying any variables will disable all output
        by setting all of MAGICC's ``out_xx`` flags to ``0``.

        This convenience function should not be confused with ``set_config`` or
        ``update_config`` which allow the user to set/update the configuration flags
        directly, without the more convenient syntax and default behaviour provided by
        this function.

        Parameters
        ----------
        write_ascii : bool
            If true, MAGICC is configured to write output files as human readable ascii files.

        write_binary : bool
            If true, MAGICC is configured to write binary output files. These files are much faster
            to process and write, but are not human readable.

        **kwargs:
            List of variables to write out. A list of possible options are as follows. This
            may not be a complete list.

            'emissions',
            'gwpemissions',
            'sum_gwpemissions',
            'concentrations',
            'carboncycle',
            'forcing',
            'surfaceforcing',
            'permafrost',
            'temperature',
            'sealevel',
            'parameters',
            'misc',
            'lifetimes',
            'timeseriesmix',
            'rcpdata',
            'summaryidx',
            'inverseemis',
            'tempoceanlayers',
            'oceanarea',
            'heatuptake',
            'warnings',
            'precipinput',
            'aogcmtuning',
            'ccycletuning',
            'observationaltuning',
            'keydata_1',
            'keydata_2'
        """

        if not (write_ascii or write_binary):
            raise AssertionError("write_binary and/or write_ascii must be configured")

        if write_binary and write_ascii:
            ascii_binary = "BOTH"
        elif write_ascii:
            ascii_binary = "ASCII"
        else:
            ascii_binary = "BINARY"

        # defaults
        outconfig = {
            "out_emissions": 0,
            "out_gwpemissions": 0,
            "out_sum_gwpemissions": 0,
            "out_concentrations": 0,
            "out_carboncycle": 0,
            "out_forcing": 0,
            "out_surfaceforcing": 0,
            "out_permafrost": 0,
            "out_temperature": 0,
            "out_sealevel": 0,
            "out_parameters": 0,
            "out_misc": 0,
            "out_timeseriesmix": 0,
            "out_rcpdata": 0,
            "out_summaryidx": 0,
            "out_inverseemis": 0,
            "out_tempoceanlayers": 0,
            "out_heatuptake": 0,
            "out_ascii_binary": ascii_binary,
            "out_warnings": 0,
            "out_precipinput": 0,
            "out_aogcmtuning": 0,
            "out_ccycletuning": 0,
            "out_observationaltuning": 0,
            "out_keydata_1": 0,
            "out_keydata_2": 0,
        }
        if self.version == 7:
            outconfig["out_oceanarea"] = 0
            outconfig["out_lifetimes"] = 0

        for kw in kwargs:
            val = 1 if kwargs[kw] else 0  # convert values to 0/1 instead of booleans
            outconfig["out_" + kw.lower()] = val

        self.update_config(**outconfig)

    def get_executable(self):
        """
        Get path to MAGICC executable being used

        Returns
        -------
        str
            Path to MAGICC executable being used
        """
        return config["executable_{}".format(self.version)]

    def diagnose_tcr_ecs_tcre(self, **kwargs):
        """
        Diagnose TCR, ECS and TCRE

        The transient climate response (TCR), is the global-mean temperature response
        per unit cumulative |CO2| emissions at the time at which atmospheric |CO2|
        concentrations double in an experiment where atmospheric |CO2| concentrations
        are increased at 1% per year from pre-industrial levels (1pctCO2 experiment).

        The equilibrium climate sensitivity (ECS), is the equilibrium global-mean
        temperature response to an instantaneous doubling of atmospheric |CO2|
        concentrations (abrupt-2xCO2 experiment).

        The transient climate response to emissions (TCRE), is the global-mean
        temperature response per unit cumulative |CO2| emissions at the time at which
        atmospheric |CO2| concentrations double in the 1pctCO2 experiment.

        Please note that sometimes the run length won't be long enough to allow
        MAGICC's oceans to fully equilibrate and hence the ECS value might not be what
        you expect (it should match the value of ``core_climatesensitivity``).

        Parameters
        ----------
        **kwargs
            parameter values to use in the diagnosis e.g. ``core_climatesensitivity=4``

        Returns
        -------
        dict
            Dictionary with keys: "ecs" - the diagnosed ECS; "tcr" - the diagnosed
            TCR; "tcre" - the diagnosed TCRE; "timeseries" - the relevant model input
            and output timeseries used in the experiment i.e. atmospheric |CO2|
            concentrations, inverse |CO2| emissions, total radiative forcing and
            global-mean surface temperature
        """
        ecs_res = self.diagnose_ecs(**kwargs)
        tcr_tcre_res = self.diagnose_tcr_tcre(**kwargs)

        out = {**ecs_res, **tcr_tcre_res}
        out["timeseries"] = run_append(
            [ecs_res["timeseries"], tcr_tcre_res["timeseries"]]
        )

        return out

    def diagnose_ecs(self, **kwargs):
        """
        Diagnose ECS

        The equilibrium climate sensitivity (ECS), is the equilibrium global-mean
        temperature response to an instantaneous doubling of atmospheric |CO2|
        concentrations (abrupt-2xCO2 experiment).

        Please note that sometimes the run length won't be long enough to allow
        MAGICC's oceans to fully equilibrate and hence the ECS value might not be what
        you expect (it should match the value of ``core_climatesensitivity``).

        Parameters
        ----------
        **kwargs
            parameter values to use in the diagnosis e.g. ``core_climatesensitivity=4``

        Returns
        -------
        dict
            Dictionary with keys: "ecs" - the diagnosed ECS; "timeseries" - the
            relevant model input and output timeseries used in the experiment i.e.
            atmospheric |CO2| concentrations, inverse |CO2| emissions, total radiative
            forcing and global-mean surface temperature
        """
        self._diagnose_ecs_config_setup(**kwargs)
        timeseries = self.run(
            scenario=None,
            only=[
                "Atmospheric Concentrations|CO2",
                "Radiative Forcing",
                "Surface Temperature",
            ],
        )
        timeseries["scenario"] = "abrupt-2xCO2"

        ecs = self.get_ecs_from_diagnosis_results(timeseries)
        return {"ecs": ecs, "timeseries": timeseries}

    def diagnose_tcr_tcre(self, **kwargs):
        """
        Diagnose TCR and TCRE

        The transient climate response (TCR), is the global-mean temperature response
        per unit cumulative |CO2| emissions at the time at which atmospheric |CO2|
        concentrations double in an experiment where atmospheric |CO2| concentrations
        are increased at 1% per year from pre-industrial levels (1pctCO2 experiment).

        The transient climate response to emissions (TCRE), is the global-mean
        temperature response per unit cumulative |CO2| emissions at the time at which
        atmospheric |CO2| concentrations double in the 1pctCO2 experiment.

        Parameters
        ----------
        **kwargs
            parameter values to use in the diagnosis e.g. ``core_climatesensitivity=4``

        Returns
        -------
        dict
            Dictionary with keys: "tcr" - the diagnosed TCR; "tcre" - the diagnosed
            TCRE; "timeseries" - the relevant model input and output timeseries used
            in the experiment i.e. atmospheric |CO2| concentrations, inverse |CO2|
            emissions, total radiative forcing and global-mean surface temperature
        """
        self._diagnose_tcr_tcre_config_setup(**kwargs)
        timeseries = self.run(
            scenario=None,
            only=[
                "Atmospheric Concentrations|CO2",
                "INVERSEEMIS",
                "Radiative Forcing",
                "Surface Temperature",
            ],
        )
        # drop all the irrelevant inverse emissions
        timeseries = timeseries.filter(
            variable="Inverse Emissions*", level=1, keep=False
        )
        # drop the final year as concs stay constant from some reason,
        # MAGICC bug...
        timeseries = timeseries.filter(time=timeseries["time"].max(), keep=False)
        timeseries["scenario"] = "1pctCO2"
        tcr, tcre = self.get_tcr_tcre_from_diagnosis_results(timeseries)

        return {"tcr": tcr, "tcre": tcre, "timeseries": timeseries}

    def _diagnose_ecs_config_setup(self, **kwargs):
        self.set_years(
            startyear=1750, endyear=4200
        )  # 4200 seems to be the max I can push too without an error

        self.update_config(
            FILE_CO2_CONC="ABRUPT2XCO2_CO2_CONC.IN",
            CO2_SWITCHFROMCONC2EMIS_YEAR=30000,
            RF_TOTAL_RUNMODUS="CO2",
            RF_TOTAL_CONSTANTAFTERYR=2000,
            **kwargs,
        )

    def _diagnose_tcr_tcre_config_setup(self, **kwargs):
        self.set_years(startyear=1750, endyear=2020)

        self.update_config(
            FILE_CO2_CONC="1PCTCO2_CO2_CONC.IN",
            CO2_SWITCHFROMCONC2EMIS_YEAR=30000,
            RF_TOTAL_RUNMODUS="CO2",
            RF_TOTAL_CONSTANTAFTERYR=3000,
            OUT_INVERSEEMIS=1,
            **kwargs,
        )

    def get_ecs_from_diagnosis_results(self, results_ecs_run):
        """
        Diagnose ECS from the results of the abrupt-2xCO2 experiment

        Parameters
        ----------
        results_ecs_run : :obj:`ScmRun`
            Results of the abrupt-2xCO2 experiment, must contain atmospheric |CO2|
            concentrations, total radiative forcing and surface temperature.

        Returns
        -------
        ecs : :obj:`pint.quantity.Quantity`
            ECS diagnosed from ``results_ecs_run``
        """
        global_co2_concs = results_ecs_run.filter(
            variable="Atmospheric Concentrations|CO2", region="World"
        )
        ecs_time, ecs_start_time = self._get_ecs_ecs_start_yr_from_CO2_concs(
            global_co2_concs
        )

        global_total_rf = results_ecs_run.filter(
            variable="Radiative Forcing", region="World"
        )
        self._check_ecs_total_RF(global_total_rf, jump_time=ecs_start_time)

        global_temp = results_ecs_run.filter(
            variable="Surface Temperature", region="World"
        )
        self._check_ecs_temp(global_temp)

        ecs = float(global_temp.filter(time=ecs_time).values.squeeze())
        unit = global_temp.get_unique_meta("unit", no_duplicates=True)
        ecs = ecs * unit_registry(unit)

        return ecs

    def get_tcr_tcre_from_diagnosis_results(self, results_tcr_tcre_run):
        """
        Diagnose TCR and TCRE from the results of the 1pctCO2 experiment

        Parameters
        ----------
        results_tcr_tcre_run : :obj:`ScmRun`
            Results of the 1pctCO2 experiment, must contain atmospheric |CO2|
            concentrations, inverse |CO2| emissions, total radiative forcing and
            surface temperature.
        Returns
        -------
        tcr, tcre : :obj:`pint.quantity.Quantity`, :obj:`pint.quantity.Quantity`
            TCR and TCRE diagnosed from ``results_tcr_tcre_run``
        """
        global_co2_concs = results_tcr_tcre_run.filter(
            variable="Atmospheric Concentrations|CO2", region="World"
        )
        (tcr_time, tcr_start_time,) = self._get_tcr_tcr_start_yr_from_CO2_concs(
            global_co2_concs
        )

        if tcr_time.year != tcr_start_time.year + 70:  # pragma: no cover # emergency
            raise AssertionError("Has the definition of TCR and TCRE changed?")

        global_inverse_co2_emms = results_tcr_tcre_run.filter(
            variable="Inverse Emissions|CO2|MAGICC Fossil and Industrial",
            region="World",
        )

        global_total_rf = results_tcr_tcre_run.filter(
            variable="Radiative Forcing", region="World"
        )
        self._check_tcr_tcre_total_RF(global_total_rf, tcr_time=tcr_time)

        global_temp = results_tcr_tcre_run.filter(
            variable="Surface Temperature", region="World"
        )
        self._check_tcr_tcre_temp(global_temp)

        tcr = float(global_temp.filter(time=tcr_time).values.squeeze())
        tcr_unit = global_temp.get_unique_meta("unit", no_duplicates=True)
        tcr = tcr * unit_registry(tcr_unit)

        tcre_cumulative_emms = float(
            global_inverse_co2_emms.filter(
                year=range(tcr_start_time.year, tcr_time.year)
            ).values.sum()
        )
        emms_unit = global_inverse_co2_emms.get_unique_meta("unit", no_duplicates=True)
        years = global_inverse_co2_emms["year"].values.squeeze()
        if not np.all((years[1:] - years[:-1]) == 1):  # pragma: no cover
            raise AssertionError(
                "TCR/TCRE diagnosis assumed to be on annual timestep. Please "
                "raise an issue at "
                "https://github.com/openscm/pymagicc/issues to discuss "
                "your use case"
            )

        # can now safely assume that our simple sum has done the right thing
        tcre_cumulative_emms_unit = unit_registry(emms_unit) * unit_registry("yr")
        tcre_cumulative_emms = tcre_cumulative_emms * tcre_cumulative_emms_unit

        tcre = tcr / tcre_cumulative_emms

        return tcr, tcre

    def _get_ecs_ecs_start_yr_from_CO2_concs(self, df_co2_concs):
        co2_concs = df_co2_concs.timeseries()
        co2_conc_0 = co2_concs.iloc[0, 0]
        t_start = co2_concs.columns.min()
        t_end = co2_concs.columns.max()

        ecs_start_time = co2_concs.iloc[
            :, co2_concs.values.squeeze() > co2_conc_0
        ].columns[0]

        spin_up_co2_concs = (
            _filter_time_range(df_co2_concs, lambda x: t_start <= x < ecs_start_time)
            .timeseries()
            .values.squeeze()
        )
        if not (spin_up_co2_concs == co2_conc_0).all():
            raise ValueError(
                "The ECS CO2 concs look wrong, they are not constant before they start rising"
            )

        co2_conc_final = 2 * co2_conc_0
        eqm_co2_concs = (
            _filter_time_range(df_co2_concs, lambda x: ecs_start_time <= x <= t_end)
            .timeseries()
            .values.squeeze()
        )
        if not np.isclose(eqm_co2_concs, co2_conc_final).all():
            raise ValueError(
                "The ECS CO2 concs look wrong, they are not constant after doubling"
            )

        ecs_time = df_co2_concs["time"].iloc[-1]

        return ecs_time, ecs_start_time

    def _get_tcr_tcr_start_yr_from_CO2_concs(self, df_co2_concs):
        co2_concs = df_co2_concs.timeseries()
        co2_conc_0 = co2_concs.iloc[0, 0]
        t_start = co2_concs.columns.min()
        t_end = co2_concs.columns.max()

        tcr_start_time = co2_concs.iloc[
            :, co2_concs.values.squeeze() > co2_conc_0
        ].columns[0] - relativedelta(years=1)
        tcr_time = tcr_start_time + relativedelta(years=70)

        spin_up_co2_concs = (
            _filter_time_range(df_co2_concs, lambda x: t_start <= x <= tcr_start_time)
            .timeseries()
            .values.squeeze()
        )
        if not (spin_up_co2_concs == co2_conc_0).all():
            raise ValueError(
                "The TCR/TCRE CO2 concs look wrong, they are not constant before they start rising"
            )

        actual_rise_co2_concs = (
            _filter_time_range(df_co2_concs, lambda x: tcr_start_time <= x <= t_end)
            .timeseries()
            .values.squeeze()
        )
        # this will blow up if we switch to diagnose tcr/ecs with a monthly run...
        expected_rise_co2_concs = co2_conc_0 * 1.01 ** np.arange(
            len(actual_rise_co2_concs)
        )
        rise_co2_concs_correct = np.isclose(
            actual_rise_co2_concs, expected_rise_co2_concs
        ).all()
        if not rise_co2_concs_correct:
            raise ValueError("The TCR/TCRE CO2 concs look wrong during the rise period")

        return tcr_time, tcr_start_time

    def _check_ecs_total_RF(self, df_total_rf, jump_time):
        total_rf = df_total_rf.timeseries()
        total_rf_max = total_rf.values.squeeze().max()

        t_start = total_rf.columns.min()
        t_end = total_rf.columns.max()

        spin_up_rf = (
            _filter_time_range(df_total_rf, lambda x: t_start <= x < jump_time)
            .timeseries()
            .values.squeeze()
        )
        if not (spin_up_rf == 0).all():
            raise ValueError(
                "The ECS total radiative forcing looks wrong, it is not all zero before concentrations start rising"
            )

        eqm_rf = (
            _filter_time_range(df_total_rf, lambda x: jump_time <= x <= t_end)
            .timeseries()
            .values.squeeze()
        )
        if not (eqm_rf == total_rf_max).all():
            raise ValueError(
                "The ECS total radiative forcing looks wrong, it is not constant after concentrations double"
            )

    def _check_tcr_tcre_total_RF(self, df_total_rf, tcr_time):
        total_rf = df_total_rf.timeseries()

        t_start = total_rf.columns.min()
        tcr_start_time = tcr_time - relativedelta(years=70)

        spin_up_rf = (
            _filter_time_range(df_total_rf, lambda x: t_start <= x <= tcr_start_time)
            .timeseries()
            .values.squeeze()
        )
        if not (spin_up_rf == 0).all():
            raise ValueError(
                "The TCR/TCRE total radiative forcing looks wrong, it is not all zero before concentrations start rising"
            )

        rf_vls = total_rf.values.squeeze()
        rf_minus_previous_yr = rf_vls[1:] - rf_vls[:-1]
        if not np.all(rf_minus_previous_yr >= 0):
            raise ValueError(
                "The TCR/TCRE total radiative forcing looks wrong, it is not rising after concentrations start rising"
            )

    def _check_ecs_temp(self, df_temp):
        self._check_tcr_ecs_tcre_temp(
            df_temp, "The ECS surface temperature looks wrong, it decreases"
        )

    def _check_tcr_tcre_temp(self, df_temp):
        self._check_tcr_ecs_tcre_temp(
            df_temp, "The TCR/TCRE surface temperature looks wrong, it decreases"
        )

    def _check_tcr_ecs_tcre_temp(self, df_temp, message):
        tmp_vls = df_temp.timeseries().values.squeeze()
        tmp_minus_previous_yr = tmp_vls[1:] - tmp_vls[:-1]
        if not np.all(tmp_minus_previous_yr >= 0):
            raise ValueError(message)

    def set_emission_scenario_setup(self, scenario, config_dict):
        """Set the emissions flags correctly.

        Parameters
        ----------
        scenario : :obj:`pymagicc.io.MAGICCData`
            Scenario to run.

        config_dict : dict
            Dictionary with current input configurations which is to be validated and
            updated where necessary.

        Returns
        -------
        dict
            Updated configuration
        """
        self.write(scenario, self._scen_file_name)
        emis_flag = list(
            self._fix_legacy_keys(
                f90nml.Namelist({"nml_allcfgs": {"file_emisscen": "junk"}}),
                conflict="ignore",
            )["nml_allcfgs"].keys()
        )[0]
        config_dict[emis_flag] = self._scen_file_name

        return config_dict

    def _check_config(self):
        """
        Check config above and beyond those checked by ``self.check_config``
        """
        pass


class MAGICC6(MAGICCBase):
    version = 6
    _scen_file_name = "SCENARIO.SCEN"

    _config_renamings = {
        "file_emisscen": "file_emissionscenario",
        "fgas_files_conc": "file_fgas_conc",
        "mhalo_switchfromconc2emis_year": "mhalo_switch_conc2emis_yr",
    }

    @property
    def default_config(self):
        """
        Default configuration to use in a run
        """
        base = f90nml.read(join(self.run_dir, "MAGCFG_DEFAULTALL_69.CFG"))
        user = f90nml.read(join(self.run_dir, "MAGCFG_USER.CFG"))
        self._default_config = deepcopy(base)
        self._default_config.update(user)

        return self._default_config

    def _check_tcr_ecs_tcre_total_RF(self, df_total_rf, tcr_time, ecs_time):
        super()._check_tcr_ecs_tcre_total_RF(df_total_rf, tcr_time, ecs_time)
        # can be more careful with checks MAGICC6 only has logarithmic CO2 forcing
        # i.e. linear rise in forcing
        total_rf = df_total_rf.timeseries()
        total_rf_max = total_rf.values.squeeze().max()

        tcre_start_time = tcr_time - relativedelta(years=70)

        actual_rise_rf = (
            _filter_time_range(df_total_rf, lambda x: tcre_start_time <= x <= tcr_time)
            .timeseries()
            .values.squeeze()
        )

        # this will blow up if we switch to diagnose tcr/ecs with a monthly run...
        expected_rise_rf = total_rf_max / 70.0 * np.arange(71)
        rise_rf_correct = np.isclose(actual_rise_rf, expected_rise_rf).all()
        if not rise_rf_correct:
            raise ValueError(
                "The TCR/ECS/TCRE total radiative forcing looks wrong during the rise period"
            )

    def _check_config(self):
        cfg = self.update_config()
        if "file_emissionscenario" in cfg["nml_allcfgs"]:
            if cfg["nml_allcfgs"]["file_emissionscenario"].endswith("SCEN7"):
                self._check_failed("MAGICC6 cannot run SCEN7 files")


class MAGICC7(MAGICCBase):
    version = 7

    _config_renamings = {
        "file_emissionscenario": "file_emisscen",
        "file_fgas_conc": "fgas_files_conc",
        "mhalo_switch_conc2emis_yr": "mhalo_switchfromconc2emis_year",
    }

    def create_copy(self):
        """
        Initialises a temporary directory structure and copy of MAGICC
        configuration files and binary.

        This will also overwrite the value of all ``file_tuningmodel_x`` flags to
        ensure that Pymagicc's configurations will be read. If ``self.strict``, this
        will also overwrite the value of all ``file_emisscen_x`` flags to ensure that
        only Pymagicc's scenario input is used. This overwrite behaviour can be
        removed once the MAGICC7 binary is publicly released as we can then create a
        Pymagicc specific MAGCFG_USER.CFG rather than relying on whatever is in the
        user's current copy.
        """
        super(MAGICC7, self).create_copy()
        self.update_config(
            "MAGCFG_USER.CFG",
            **{
                "file_tuningmodel_1": "PYMAGICC",
                "file_tuningmodel_2": "USER",
                "file_tuningmodel_3": "USER",
                "file_tuningmodel_4": "USER",
                "file_tuningmodel_5": "USER",
                "file_tuningmodel_6": "USER",
                "file_tuningmodel_7": "USER",
                "file_tuningmodel_8": "USER",
                "file_tuningmodel_9": "USER",
                "file_tuningmodel_10": "USER",
            },
        )
        if self.strict:
            self.update_config(
                "MAGCFG_USER.CFG",
                **{
                    "file_emisscen_2": "NONE",
                    "file_emisscen_3": "NONE",
                    "file_emisscen_4": "NONE",
                    "file_emisscen_5": "NONE",
                    "file_emisscen_6": "NONE",
                    "file_emisscen_7": "NONE",
                    "file_emisscen_8": "NONE",
                },
            )

    def _diagnose_tcr_ecs_tcre_config_setup(self, **kwargs):
        super()._diagnose_tcr_ecs_tcre_config_setup(**kwargs)
        # also need to lock CH4 and N2O in case OLBL forcing mode is being used
        self.update_config(
            FILE_CH4_CONC="TCRECS_CH4_CONC.IN",
            CH4_SWITCHFROMCONC2EMIS_YEAR=30000,
            FILE_N2O_CONC="TCRECS_N2O_CONC.IN",
            N2O_SWITCHFROMCONC2EMIS_YEAR=30000,
        )

    def _check_config(self):
        pass


def _filter_time_range(scmdf, filter_func):
    # TODO: move into openscm
    tdf = scmdf.timeseries()
    tdf = tdf.iloc[:, tdf.columns.map(filter_func)]
    return MAGICCData(tdf)
