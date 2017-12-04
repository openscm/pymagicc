---
title: 'Pymagicc: A Python wrapper for the simple climate model MAGICC'
tags:
  - climate change
  - simple climate model
  - python-wrapper
authors:
  - name: Robert Gieseke
    orcid: 0000-0002-1236-5109
    affiliation: 1
  - name: Sven N Willner
    orcid: 0000-0001-6798-6247
    affiliation: 1, 2
  - name: ...
affiliations:
  - name: Potsdam Institute for Climate Impact Research, 14473 Potsdam, Germany
    index: 1
  - name: University of Potsdam, 14476 Potsdam, Germany
    index: 2
date: 01 December 2017
bibliography: paper.bib
output: pdf_document
---

# Summary

Pymagicc is a Python wrapper for the Fortran-based reduced-complexity
climate carbon cycle model MAGICC [@Meinshausen2011].

MAGICC (Model for the Assessment of Greenhouse Gas Induced Climate Change) has
been under development since the late 1980s and has a hemispherically averaged upwelling-diffusion ocean coupled to an atmosphere layer and a globally averaged carbon cycle model.

The MAGICC^[http://magicc.org] model has been used to emulate complex
atmosphere-ocean general circulation models (AOGCM) runs from the Coupled
Model Intercomparison Projects^[https://cmip.llnl.gov/].
It is also widely used as the climate component in Integrated Assessment Models (IAMs) and in the assessment of future emissions pathways in climate policy analyses.

The Pymagicc tool simplifies usage of the model by integrating it into the
scientific Python system and by facilitating comparisons with other recently
published simple climate models written in Python, such as
@Gasser2017, @Willner17, and @Millar2017.
The emissions scenarios used as input to Pymagicc
use DataFrames from the Pandas library [@McKinney2010] for creating and
modifying of scenarios.
To read and write MAGICC configuration and output files in the Fortran Namelist format Pymagicc utilizes the f90nml^[https://github.com/marshallward/f90nml] library.
All MAGICC model parameters can be modified when running the model.

Pymagicc can be installed using `pip` from the Python Package Index ^[<https://pypi.python.org/pypi/pymagicc>].
The MAGICC binary, released under a
Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported
License^[https://creativecommons.org/licenses/by-nc-sa/3.0/], has been compiled
for the Windows operating system. To enable it to run under Linux and macOS the
Wine^[https://www.winehq.org/] compatibility layer is used in Pymagicc.

Source code, usage documentation and issue tracker are available in Pymagicc's GitHub
repository^[<https://github.com/openclimatedata/pymagicc>].
Usage examples are also contained in the repository as a Jupyter Notebook [@Perez2007; @Kluyver2016]. Thanks to the Binder project^[<https://mybinder.org/>], the example
Notebook can also be used and explored without having to locally install Pymagicc.

# References
