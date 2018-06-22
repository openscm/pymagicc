import shutil
import subprocess
from distutils import dir_util
from os import listdir, makedirs
from os.path import basename, dirname, exists, join
from tempfile import mkdtemp

import f90nml
import pandas as pd

from .config import config

IS_WINDOWS = config['is_windows']


class MAGICC(object):
    """
    Provides access to the MAGICC binary and configuration.

    To enable multiple MAGICC 'packages' to be configured independently,
    the MAGICC directory containing the input files, configuration
    and binary is copied to a new folder. The configuration in this
    MAGICC copy can then be edited without impacting other instances.

    A `MAGICC` instance first has to be setup by calling
    `create_copy`. If many model runs are being performed this step only has
    to be performed once. `run` can be called many times with the
    configuration files being updated between each call.

    Alternatively, an existing MAGICC directory structure can be used by
    setting `root_dir`.
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
        # Copy the MAGICC run directory into the appropriate location
        dir_util.copy_tree(join(self.original_dir, ".."), self.root_dir)

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
                    if isinstance(v, str):
                        parameters[group][k] = v.strip()
                    elif isinstance(v, list):
                        if isinstance(v[0], str):
                            parameters[group][k] = [
                                i.strip().replace("\n", "") for i in v]
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


class MAGICC6(MAGICC):
    version = 6

    def get_executable(cls):
        return config['executable']


class MAGICC7(MAGICC):
    version = 7

    def get_executable(cls):
        return config['executable_7']
