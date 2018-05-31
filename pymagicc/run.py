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


class ModelRun(object):
    def __init__(self, root_dir=None):
        self.root_dir = root_dir
        self.config = {}
        self.init_root(self.root_dir)

    def init_root(self, root_dir):
        """
        Initialise the directory structure and copy in MAGICC
        """
        if root_dir is not None:
            self.is_temp = False
            if not exists(root_dir):
                makedirs(root_dir)
        else:
            # Create a temp directory
            self.is_temp = True
            self.root_dir = mkdtemp(prefix="pymagicc-")

        # Copy the MAGICC run directory into the appropriate location
        dir_util.copy_tree(_magiccpath, self.run_dir)
        if not exists(self.out_dir):
            makedirs(self.out_dir)

    @property
    def run_dir(self):
        return join(self.root_dir, 'run')

    @property
    def out_dir(self):
        return join(self.root_dir, 'out')

    def run(self, only=None):
        """
        Run MAGICC

        :param only: If not None, only extract variables in this list
        :return:
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

        if self.is_temp:
            shutil.rmtree(self.root_dir)

        return results
