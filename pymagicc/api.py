import shutil
import subprocess
from os import listdir, makedirs
from os.path import basename, dirname, exists, join, isfile, abspath
from tempfile import mkdtemp

import numpy as np
import pandas as pd
import f90nml

from .config import config

IS_WINDOWS = config["is_windows"]


def _copy_files(source, target):
    """
    Copy all the files in source directory to target

    Ignores subdirectories
    """
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

    A `MAGICC` instance first has to be setup by calling
    `create_copy`. If many model runs are being performed this step only has
    to be performed once. The `run` method can then be called many times
    without re-copying the files each time. Between each call to `run`, the
    configuration files can be updated to perform runs with different
    configurations.

    # Parameters
    root_dir (str): If `root_dir` is supplied, an existing MAGICC 'setup' is
        used.
    """

    version = None

    def __init__(self, root_dir=None):
        self.root_dir = root_dir
        self.config = {}
        self.executable = self.get_executable()

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

    def get_executable(self):
        raise NotImplementedError

    def create_copy(self):
        """
        Initialises a temporary directory structure and copy of MAGICC
        configuration files and binary.
        """
        if self.executable is None or not isfile(self.executable):
            raise FileNotFoundError(
                "Could not find MAGICC{} executable: {}".format(
                    self.version, self.executable
                )
            )
        if self.is_temp:
            assert (
                self.root_dir is None
            ), "A temp copy for this instance has already been created"
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
        dirs_to_copy = [".", "bin", "run"]
        # Check that the executable is in a valid sub directory
        assert exec_dir in dirs_to_copy, "binary must be in bin/ or run/ directory"

        for d in dirs_to_copy:
            source_dir = abspath(join(self.original_dir, "..", d))
            if exists(source_dir):
                _copy_files(source_dir, join(self.root_dir, d))

        # Create an empty out dir
        # MAGICC assumes that the 'out' directory already exists
        makedirs(join(self.root_dir, "out"))

        # Create basic configuration files so magicc can run
        self.set_years()
        self.set_config()

    @property
    def binary_name(self):
        return basename(self.executable)

    @property
    def original_dir(self):
        return dirname(self.executable)

    @property
    def run_dir(self):
        if self.root_dir is None:
            return None
        return join(self.root_dir, "run")

    @property
    def out_dir(self):
        if self.root_dir is None:
            return None
        return join(self.root_dir, "out")

    def run(self, only=None):
        """
        Run MAGICC and parse the output.

        :param only: If not None, only extract variables in this list
        :return: Dict containing DataFrames for each of the extracted variables
        """
        if not exists(self.root_dir):
            raise FileNotFoundError(self.root_dir)

        exec_dir = basename(self.original_dir)
        command = [join(self.root_dir, exec_dir, self.binary_name)]

        if not IS_WINDOWS and self.binary_name.endswith(".exe"):  # pragma: no cover
            command.insert(0, "wine")

        # On Windows shell=True is required.
        subprocess.check_call(command, cwd=self.run_dir, shell=IS_WINDOWS)

        results = {}

        outfiles = [
            f
            for f in listdir(self.out_dir)
            if f.startswith(("DAT_", "CARBONCYCLE")) and f.endswith(".OUT")
        ]

        for filename in outfiles:
            name = filename.replace("DAT_", "").replace(".OUT", "")
            if self.version == 6:
                skiprows = 19
            else:
                skiprows = 21
            if only is None or name in only:
                results[name] = pd.read_csv(
                    join(self.out_dir, filename),
                    delim_whitespace=True,
                    skiprows=skiprows,
                    index_col=0,
                    engine="python",
                )

        with open(join(self.out_dir, "PARAMETERS.OUT")) as nml_file:
            parameters = dict(f90nml.read(nml_file))
            for group in ["nml_years", "nml_allcfgs", "nml_outputcfgs"]:
                parameters[group] = dict(parameters[group])
                for k, v in parameters[group].items():
                    parameters[group][k] = _clean_value(v)
                parameters[group.replace("nml_", "")] = parameters.pop(group)
            self.config = parameters

        return results

    def remove_temp_copy(self):
        """
        Removes a temporary copy of the MAGICC version shipped with Pymagicc.
        """
        if self.is_temp and self.root_dir is not None:
            shutil.rmtree(self.root_dir)
            self.root_dir = None

    def set_config(
        self, filename="MAGTUNE_PYMAGICC.CFG", top_level_key="nml_allcfgs", **kwargs
    ):
        """
        Create a configuration file for MAGICC

        Writes a fortran namelist in run_dir.

        # Parameters
        filename (str): Name of configuration file to write
        top_level_key (str): Name of namelist to be written in the
            configuration file
        kwargs: Other parameters to pass to the configuration file. No
            validation on the parameters is performed.

        # Returns
        data (dict): The contents of the namelist which was written to file
        """
        fname = join(self.run_dir, filename)
        data = {top_level_key: kwargs}
        f90nml.write(data, fname, force=True)

        return data

    def set_years(self, startyear=1765, endyear=2100):
        """
        Set the start and end dates of the simulations

        :param startyear: Start year of the simulation
        :param endyear: End year of the simulation
        :return: The contents of the namelist
        """
        # stepsperyear is required and should never be overridden
        return self.set_config(
            "MAGCFG_NMLYEARS.CFG",
            "nml_years",
            endyear=endyear,
            startyear=startyear,
            stepsperyear=12,
        )

    def get_executable(self):
        return config["executable_{}".format(self.version)]

    def diagnose_tcr_ecs(self, **kwargs):
        self._diagnose_tcr_ecs_config_setup(**kwargs)
        timeseries = self.run(
            only=["CO2_CONC", "TOTAL_INCLVOLCANIC_RF", "SURFACE_TEMP"]
        )
        tcr, ecs = self._get_tcr_ecs_from_diagnosis_results(timeseries)
        return {"tcr": tcr, "ecs": ecs, "timeseries": timeseries}

    def _diagnose_tcr_ecs_config_setup(self, **kwargs):
        self.set_years(
            startyear=1750, endyear=4200
        )  # 4200 seems to be the max I can push too without an error

        self.set_config(
            FILE_CO2_CONC="TCRECS_CO2_CONC.IN",
            RF_TOTAL_RUNMODUS="CO2",
            RF_TOTAL_CONSTANTAFTERYR=2000,
            **kwargs,
        )

    def _get_tcr_ecs_from_diagnosis_results(self, results_tcr_ecs_run):
        tcr_yr, ecs_yr = self._get_tcr_ecs_yr_from_CO2_concs(
            results_tcr_ecs_run["CO2_CONC"]["GLOBAL"]
        )
        self._check_tcr_ecs_total_RF(
            results_tcr_ecs_run["TOTAL_INCLVOLCANIC_RF"]["GLOBAL"],
            tcr_yr=tcr_yr,
            ecs_yr=ecs_yr,
        )
        self._check_tcr_ecs_temp(results_tcr_ecs_run["SURFACE_TEMP"]["GLOBAL"])
        tcr = results_tcr_ecs_run["SURFACE_TEMP"]["GLOBAL"].loc[tcr_yr]
        ecs = results_tcr_ecs_run["SURFACE_TEMP"]["GLOBAL"].loc[ecs_yr]
        return tcr, ecs

    def _get_tcr_ecs_yr_from_CO2_concs(self, df_co2_concs):
        co2_conc_0 = df_co2_concs.iloc[0]
        yr_start_rise = -1 + df_co2_concs[df_co2_concs.gt(co2_conc_0)].index[0]
        tcr_yr = yr_start_rise + 70
        spin_up_co2_concs = df_co2_concs.loc[:yr_start_rise]
        if not (spin_up_co2_concs == co2_conc_0).all():
            raise ValueError(
                "The TCR/ECS CO2 concs look wrong, they are not constant before they start rising"
            )

        actual_rise_co2_concs = df_co2_concs.loc[
            yr_start_rise : yr_start_rise + 70
        ].values
        expected_rise_co2_concs = co2_conc_0 * 1.01 ** np.arange(71)
        rise_co2_concs_correct = np.isclose(
            actual_rise_co2_concs, expected_rise_co2_concs
        ).all()
        if not rise_co2_concs_correct:
            raise ValueError("The TCR/ECS CO2 concs look wrong during the rise period")

        co2_conc_final = max(expected_rise_co2_concs)
        eqm_co2_concs = df_co2_concs.loc[tcr_yr:]
        if not np.isclose(eqm_co2_concs, co2_conc_final).all():
            raise ValueError(
                "The TCR/ECS CO2 concs look wrong, they are not constant after 70 years of rising"
            )

        ecs_yr = df_co2_concs.index[-1]

        return tcr_yr, ecs_yr

    def _check_tcr_ecs_total_RF(self, df_total_rf, tcr_yr, ecs_yr):
        if not (df_total_rf.loc[: tcr_yr - 70] == 0).all():
            raise ValueError(
                "The TCR/ECS total radiative forcing looks wrong, it is not all zero before concentrations start rising"
            )

        total_rf_max = df_total_rf.max()
        actual_rise_rf = df_total_rf.loc[tcr_yr - 70 : tcr_yr].values
        expected_rise_rf = total_rf_max / 70. * np.arange(71)
        rise_rf_correct = np.isclose(actual_rise_rf, expected_rise_rf).all()
        if not rise_rf_correct:
            raise ValueError(
                "The TCR/ECS total radiative forcing looks wrong during the rise period"
            )

        if not (df_total_rf.loc[tcr_yr:] == total_rf_max).all():
            raise ValueError(
                "The TCR/ECS total radiative forcing looks wrong, it is not constant after concentrations are constant"
            )

    def _check_tcr_ecs_temp(self, df_temp):
        tmp_vls = df_temp.values
        tmp_minus_previous_yr = tmp_vls[1:] - tmp_vls[:-1]
        if not np.all(tmp_minus_previous_yr >= 0):
            raise ValueError(
                "The TCR/ECS surface temperature looks wrong, it decreases"
            )


class MAGICC6(MAGICCBase):
    version = 6


class MAGICC7(MAGICCBase):
    version = 7
