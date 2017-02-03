import os

import matplotlib.pyplot as plt
plt.style.use("ggplot")
plt.rcParams["figure.figsize"] = 10, 5
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.size"] = 12

import pymagicc
from pymagicc import rcp3pd, rcp45, rcp6, rcp85

path = os.path.join(os.path.dirname(__file__),
                    './example-plot.png')

for rcp in  [rcp3pd, rcp45, rcp6, rcp85]:
    results, _ = pymagicc.run(rcp)
    temp = results.SURFACE_TEMP.GLOBAL.loc[1850:] - \
        results.SURFACE_TEMP.GLOBAL.loc[1850:1900].mean()
    temp.plot(label=rcp.name)

plt.title("Global mean temperature")
plt.ylabel("°C over pre-industrial (1850-1900 mean)")
plt.legend(loc="best")

plt.savefig(path, dpi=96)
