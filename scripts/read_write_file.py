"""A simple script that can be used to read and write a file to see the effects of the formatting without having to always stop and debug tests
"""

import os
from os.path import join, expanduser

from pymagicc.io import MAGICCData

here = os.path.dirname(os.path.abspath(__file__))
fpath = join(here, "..", "pymagicc", "MAGICC6", "run")
fname = "RCP26.SCEN"

mi_writer = MAGICCData()
mi_writer.read(filepath=fpath, filename=fname)

mi_writer.write(join(expanduser("~"), fname))
