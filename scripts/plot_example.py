import os
import matplotlib.pyplot as plt
import pymagicc

from pymagicc import scenarios

plt.style.use("ggplot")
plt.rcParams["figure.figsize"] = 10, 5
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.size"] = 12


path = os.path.join(os.path.dirname(__file__),
                    './example-plot.png')

for name, scen in scenarios.items():
    results, params = pymagicc.run(scen, return_config=True)
    temp = (results["SURFACE_TEMP"].GLOBAL.loc[1850:] -
            results["SURFACE_TEMP"].GLOBAL.loc[1850:1900].mean())
    temp.plot(label=name)

plt.legend()
plt.title("Global Mean Temperature Projection")
plt.ylabel(u"°C over pre-industrial (1850-1900 mean)")
plt.legend(loc="best")

plt.savefig(path, dpi=96)
