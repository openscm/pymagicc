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
  - name: Matthias Mengel
    orcid: 0000-0001-6724-9685
    affiliation: 1
affiliations:
  - name: Potsdam Institute for Climate Impact Research, 14473 Potsdam, Germany
    index: 1
  - name: University of Potsdam, 14476 Potsdam, Germany
    index: 2
date: 13 December 2017
bibliography: paper.bib
output: pdf_document
---

# Summary

Pymagicc is a Python interface for the Fortran-based reduced-complexity climate carbon cycle model MAGICC [@Meinshausen2011].
Aiming at broadening the user base of MAGICC^[http://magicc.org], Pymagicc provides a wrapper around the MAGICC binary^[http://magicc.org/download6], which runs on Windows and has been published under a Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported License^[https://creativecommons.org/licenses/by-nc-sa/3.0/]. Pymagicc itself is licensed under the GNU Affero General Public License v3.0^[https://www.gnu.org/licenses/#AGPL].

Pymagicc runs on Windows, macOS and Linux and simplifies usage of the model by utilising DataFrames from the Pandas library [@McKinney2010] as a data structure for emissions scenarios.
To read and write the text-based MAGICC configuration and output files in the Fortran Namelist format Pymagicc utilizes the f90nml library [@Ward2017].
All MAGICC model parameters and emissions scenarios can thus easily be modified through Pymagicc from Python.

MAGICC (Model for the Assessment of Greenhouse Gas Induced Climate Change)
is widely used in the assessment of future emissions pathways in climate policy analyses,
e.g. in the Fifth Assessment Report of the
Intergovernmental Panel on Climate Change [@IPCC2014]. Many Integrated Assessment Models (IAMs) utilize
MAGICC to model the physical aspects of climate change.
It has also been used to emulate complex
atmosphere-ocean general circulation models (AOGCM) from the Coupled
Model Intercomparison Projects^[https://cmip.llnl.gov/].

Pymagicc also facilitates comparisons with other recently published simple climate models available from or written in Python, such as OSCAR^[https://github.com/tgasser/OSCAR] (@Gasser2017), Pyhector^[https://github.com/openclimatedata/pyhector] (@Willner17, @Hartin2015), and FAIR^[https://github.com/OMS-NetZero/FAIR] (@Millar2017.)

It can be installed using `pip` from the Python Package Index ^[<https://pypi.python.org/pypi/pymagicc>].
To enable Pymagicc to run under Linux and macOS the Wine^[https://www.winehq.org/] compatibility layer is used, usually being available from package managers.

Source code, documentation and issue tracker are available in Pymagicc's GitHub
repository^[<https://github.com/openscm/pymagicc>].
Usage examples are also contained in the repository as a Jupyter Notebook [@Perez2007; @Kluyver2016]. Thanks to the Binder project^[<https://mybinder.org/>], the example
Notebook can also be run interactively and explored without the need to install Pymagicc locally.

## Acknowledgements

We thank the authors of MAGICC for making the binary available under a Creative Commons
license and Johannes Gütschow and Louise Jeffery for helpful comments on earlier
versions of Pymagicc and the manuscript.

# References
