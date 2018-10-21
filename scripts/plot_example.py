import os
import matplotlib.pyplot as plt


import pymagicc
from pymagicc import scenarios


plt.style.use("ggplot")
plt.rcParams["figure.figsize"] = 10, 5
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.size"] = 12


output_path = os.path.join(
    os.path.dirname(__file__),
    './example-plot.png'
)

for name, scen in scenarios.items():
    results = pymagicc.run(scen)
    results_df = results.df
    results_df.set_index("time", inplace=True)

    global_temp_time_rows = (
        (results_df.variable == "Surface Temperature")
        & (results_df.region == "World")
    )

    temp = (
        results_df.value[global_temp_time_rows].loc[1850:]
        - results_df.value[global_temp_time_rows].loc[1850:1900].mean()
    )
    temp.plot(label=name)

plt.legend()
plt.title("Global Mean Temperature Projection")
plt.ylabel("°C over pre-industrial (1850-1900 mean)");
plt.legend(loc="best")

plt.savefig(output_path, dpi=96)
