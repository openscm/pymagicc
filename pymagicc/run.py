import platform
import shutil
import subprocess
from distutils import dir_util
from os import listdir, makedirs
from os.path import join, exists
from tempfile import mkdtemp

import f90nml
import pandas as pd

from .compat import get_param
from .paths import _magiccbinary, _magiccpath

_WINDOWS = platform.system() == "Windows"


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

    def __init__(self, root_dir=None):
        self.root_dir = root_dir
        self.config = {}

        if root_dir is not None:
            self.is_temp = False
        else:
            # Create a temp directory
            self.is_temp = True
            self.root_dir = mkdtemp(prefix="pymagicc-")

    def __enter__(self):
        if self.is_temp and not exists(self.run_dir):
            self.create_copy()
        return self

    def __exit__(self, *args, **kwargs):
        if self.is_temp:
            self.remove_temp_copy()

    def create_copy(self):
        """
        Initialises a temporary directory structure and copy of MAGICC
        configuration files and binary.
        """
        if exists(self.run_dir):
            raise FileExistsError("A copy of MAGICC has already been created.")
        elif not exists(self.root_dir):
            makedirs(self.root_dir)
        # Copy the MAGICC run directory into the appropriate location
        dir_util.copy_tree(join(_magiccpath, ".."), self.root_dir)

    @property
    def run_dir(self):
        return join(self.root_dir, 'run')

    @property
    def out_dir(self):
        return join(self.root_dir, 'out')

    def run(self, only=None):
        """
        Run MAGICC and parse the output.

        :param only: If not None, only extract variables in this list
        :return: Dict containing DataFrames for each of the extracted variables
        """
        command = [join(self.run_dir, _magiccbinary)]

        if not _WINDOWS and _magiccbinary.endswith(".exe"):  # pragma: no cover
            command.insert(0, 'wine')

        # On Windows shell=True is required.
        subprocess.check_call(command, cwd=self.run_dir, shell=_WINDOWS)

        results = {}

        outfiles = [f for f in listdir(self.out_dir)
                    if f.startswith("DAT_") and f.endswith(".OUT")]

        for filename in outfiles:
            name = filename.replace("DAT_", "").replace(".OUT", "")
            if only is None or name in only:
                results[name] = pd.read_csv(
                    join(self.out_dir, filename),
                    delim_whitespace=True,
                    skiprows=get_param('num_output_headers'),
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
