from os import listdir
from os.path import join, dirname

from pymagicc.input import MAGICCInput

MAGICC6_DIR = join(dirname(__file__), "..", "pymagicc", "MAGICC6", "run")

mdata = MAGICCInput()

cant_read = []
for file in listdir(MAGICC6_DIR):
    if file.endswith((".exe")):
        continue
    try:
        mdata.read(MAGICC6_DIR, file)
    except Exception:
        cant_read.append(file)


if cant_read:
    print("Cannot yet read\n{}".format("\n".join(cant_read)))
else:
    print("Success! Can read all files in {}".format(MAGICC6_DIR))
