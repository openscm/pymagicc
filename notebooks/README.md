# Pymagicc Jupyter Notebooks

This directory contains [Jupyter](http://jupyter.org/) example Notebooks.

[Example.ipynb](./Example.ipynb) shows some examples on how to use and run Pymagicc.

[Demo.ipynb](./Demo.ipynb) is an interactive demo app, built using the
[appmode](https://github.com/oschuett/appmode/) extension.
To install its dependencies beyond the usual `notebook` and `matplotlib` one
needs to run:

    pip install ipywidgets appmode
    jupyter nbextension enable --py --sys-prefix widgetsnbextension
    jupyter nbextension     enable --py --sys-prefix appmode
    jupyter serverextension enable --py --sys-prefix appmode

The Demo notebook will not display properly in the GitHub preview and needs
to be run locally or on Binder.
