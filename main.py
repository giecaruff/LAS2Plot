import json
import yaml
import matplotlib.pyplot as plt

import las2
from logplot import LogPlot
from data_provider import DataProvider
from logplot_template import parse as parse_template


def get_well_name(lasfile):
    for row in lasfile["well"]:
        if row["mnemonic"] == "WELL":
            well_name = row["value"]
    
    return well_name

print("Loading configuration file.")

with open("config.json", "r") as f:
    config = json.load(f)

lasfilepath = config["lasfile"].pop("path")
templatepath = config["template"].pop("path")
templateformat = templatepath.split(".")[-1]

print("Reading LAS file.")

lasfile = las2.read(lasfilepath)

print("Reading template file.")

if templateformat == "appy":
    with open(templatepath, "r") as f:
        template = yaml.safe_load(f)
elif templateformat == "json":
    with open(templatepath, "r") as f:
        template = json.load(f)
else:
    raise NotImplementedError(f"Not valid template file format: {templateformat}")

dataprovider = DataProvider(lasfile)
template = parse_template(template)

well_name = get_well_name(lasfile)

print("Loading the view.")

fig = plt.figure()
plt.gcf().canvas.manager.set_window_title(well_name)
try:
    logplot = LogPlot(dataprovider, template, fig)
    logplot.draw()

    plt.show()
except Exception:
    raise
finally:
    plt.close(fig)

print("Closing program.")
