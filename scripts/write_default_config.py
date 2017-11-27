import pymagicc
from pathlib import Path

root = Path(__file__).parents[1]

_, conf = pymagicc.run(pymagicc.rcp45, return_config=True)

conf["allcfgs"]["rundate"] = "No date specified."

conf.write(str(root / "pymagicc/default_config.nml"), force=True)
