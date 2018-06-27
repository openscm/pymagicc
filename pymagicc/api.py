import shutil
import subprocess
from os import listdir, makedirs
from os.path import basename, dirname, exists, join, isfile
from tempfile import mkdtemp

import f90nml
import pandas as pd

from .config import config

IS_WINDOWS = config['is_windows']


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
            return [
                i.replace("\0", "").strip().replace("\n", "") for i in v
            ]
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

    def create_copy(self):
        """
        Initialises a temporary directory structure and copy of MAGICC
        configuration files and binary.
        """
        if self.is_temp:
            assert self.root_dir is None, "A temp copy for this instance has already been created"
            self.root_dir = mkdtemp(prefix="pymagicc-")

        if exists(self.run_dir):
            raise Exception("A copy of MAGICC has already been created.")
        if not exists(self.root_dir):
            makedirs(self.root_dir)

        # Copy a subset of folders from the MAGICC `original_dir`
        # Also copy anything which is in the root of the MAGICC distribution
        # Assumes that the MAGICC binary is in a folder one level below the root
        # of the MAGICC distribution. i.e. /run/magicc.exe or /bin/magicc
        dirs_to_copy = [
            '.',
            'bin',
            'run'
        ]
        for d in dirs_to_copy:
            source_dir = join(self.original_dir, '..', d)
            if exists(source_dir):
                _copy_files(source_dir, join(self.root_dir, d))

        # Create an empty out dir
        # MAGICC assumes that the 'out' directory already exists
        makedirs(join(self.root_dir, 'out'))

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
        return join(self.root_dir, 'run')

    @property
    def out_dir(self):
        if self.root_dir is None:
            return None
        return join(self.root_dir, 'out')

    def run(self, only=None):
        """
        Run MAGICC and parse the output.

        :param only: If not None, only extract variables in this list
        :return: Dict containing DataFrames for each of the extracted variables
        """
        command = [join(self.run_dir, self.binary_name)]

        if not IS_WINDOWS \
                and self.binary_name.endswith(".exe"):  # pragma: no cover
            command.insert(0, 'wine')

        # On Windows shell=True is required.
        subprocess.check_call(command, cwd=self.run_dir, shell=IS_WINDOWS)

        results = {}

        outfiles = [f for f in listdir(self.out_dir)
                    if f.startswith("DAT_") and f.endswith(".OUT")]

        for filename in outfiles:
            name = filename.replace("DAT_", "").replace(".OUT", "")
            if only is None or name in only:
                results[name] = pd.read_csv(
                    join(self.out_dir, filename),
                    delim_whitespace=True,
                    skiprows=19 if self.version == 6 else 21,
                    index_col=0,
                    engine="python"
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
        if self.is_temp:
            shutil.rmtree(self.root_dir)
            self.root_dir = None

    def set_config(self, filename='MAGTUNE_SIMPLE.CFG',
                   top_level_key='nml_allcfgs', **kwargs):
        """
        Create a configuration file for MAGICC

        Writes a fortran namelist in run_dir.
        :param filename:
        :param top_level_key:
        :param kwargs: Other parameters to pass to the configuration file. No
            validation on the parameters is performed.
        :return: A dict containing the contents of the namelist which was
            written to file
        """
        fname = join(self.run_dir, filename)
        data = {
            top_level_key: kwargs
        }
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
        return self.set_config('MAGCFG_NMLYEARS.CFG', 'nml_years',
                               endyear=endyear, startyear=startyear,
                               stepsperyear=12)


class MAGICC6(MAGICCBase):
    version = 6

    def get_executable(cls):
        return config['executable']


class MAGICC7(MAGICCBase):
    version = 7

    def get_executable(cls):
        return config['executable_7']
