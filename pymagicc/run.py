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
    A working copy of the MAGICC binary and configuration.

    To enable multiple MAGICC 'Packages' to be configured independently,
    the MAGICC run directory containing the input files, configuration
    and binary is copied to a new folder. The configuration in this
    MAGICC can then be edited without impacting other instances of MAGICC.

    A `MAGICC` first has to be initialised by calling `init` to perform
    this copy. If many model runs are being performed this step only has
    to be performed once. `run` can be called many times with the
    configuration files being updated between each call. Many independent
    instances of MAGICC with the same `root_dir` can be created/destroyed
    as long as `init` is only called once or any changes to the
    MAGICC will be lost.
    """

    def __init__(self, root_dir=None):
        self.root_dir = root_dir
        self.config = {}

        if root_dir is not None:
            self.is_temp = False
            if not exists(root_dir):
                makedirs(root_dir)
        else:
            # Create a temp directory
            self.is_temp = True
            self.root_dir = mkdtemp(prefix="pymagicc-")

    def __enter__(self):
        if not self.is_initialised():
            self.init()
        return self

    def __exit__(self, *args, **kwargs):
        self.close()

    def init(self):
        """
        Initialise the directory structure and copy in MAGICC configuration
        and binary.

        This overwrites any configuration changes in the run directory.
        """
        # Copy the MAGICC run directory into the appropriate location
        dir_util.copy_tree(_magiccpath, self.run_dir)
        if not exists(self.out_dir):
            makedirs(self.out_dir)

    def is_initialised(self):
        """
        Checks to see if the run directory has been previously initialised
        """
        return exists(self.run_dir) and exists(self.out_dir)

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

        if not _WINDOWS and _magiccbinary.endswith(".exe"):
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

    def close(self):
        """
        Cleans up the package's root directory.

        If no root_dir was provided, than the temporary MAGICC directory
        is deleted.
        """
        if self.is_temp:
            shutil.rmtree(self.root_dir)
