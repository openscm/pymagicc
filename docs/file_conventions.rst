MAGICC file conventions
=======================

Input files
-----------

The MAGICC ``run`` directory contains all of MAGICC’s input files. At
the moment, we have only tested reading of these files. Hence whilst we
can also write these files, we make no guarantee that having written
them, they will a) run MAGICC or b) be handled in the expected way.

The files in the ``run`` directory follow a number of conventions, we
summarise these here (please note that this is just a summary, we are
still unsure about how strictly many of these conventions have to be
followed as we are yet to set up tests for running MAGICC with all of
these different files after they’ve been set using pymagicc, the key
question we still need to answer is how important column order is in
each of these files).

1. Files ending in ``.SCEN`` are emissions scenario files. They are used
   to drive MAGICC6 and can also be used to drive MAGICC7, although it
   is much less predictable with MAGICC7.
2. Files ending in ``.SCEN7`` and ``.IN`` are other input files. They
   are both the same format, some notes, then the data in space
   separated columns.

   1. Files ending in ``.SCEN7`` are scenario input files.
   2. Files ending in ``.IN`` are input files, typically related to the
      historical period. The filename indicates what data is in the file
      e.g. ``CONC.IN`` indicates that this file contains concentrations.

3. Files ending in ``.CFG`` are config files. They are used to set
   MAGICC’s configuration and are always in the format of a FORTRAN90
   namelist.
4. Files ending in ``.prn`` are emissions input files for ozone
   depleting substances. This file format is comprised of a header row
   which contains (unlabelled) information about the first data row,
   start year and end year, then some notes rows, then the data in fixed
   width columns. This file format is used by MAGICC6 but has been
   deprecated for MAGICC7 in favour of ``*EMIS.IN`` and ``*.SCEN7``
   files.


Columns
+++++++

In MAGICC data and input files there are a number of columns, each of which is explained here.

- variable: the variable for which the data applies

- region: the region in which the data applies

- units: the units of the data

- time: the point in time at which the data occurs

    - note that the internal convention is that state variables are start of year values (i.e. 1st January 1990) whilst fluxes are annual averages/midyear values

- set: a MAGICC flag which defines what MAGICC should do with the data in the timeseries

    - SET: set the given variable in the given region to the value provided (standard setting)
    - ADD: add the data for the given variable in the given region to any already read in data for that variable in that region (although it is not clear to the authors of Pymagicc how exactly to use this flag)
    - SUBTRACT: subtract the data for the given variable in the given region from any already read in data for that variable in that region (although it is not clear to the authors of Pymagicc how exactly to use this flag)


Namelists
---------

At the top of each input file there is a namelist called ``thisfile_specifications``. It looks something like this

.. code:: Fortran

   &THISFILE_SPECIFICATIONS
    THISFILE_DATACOLUMNS    =    7  ,
    THISFILE_DATAROWS       =  266  ,
    THISFILE_FIRSTYEAR      = 1750  ,
    THISFILE_LASTYEAR       = 2015  ,
    THISFILE_ANNUALSTEPS    =    1  ,
    THISFILE_FIRSTDATAROW   =   99  ,
    THISFILE_UNITS          = "kt"  ,
    THISFILE_DATTYPE        = "REGIONDATA"  ,
    THISFILE_REGIONMODE     = "RCPPLUSBUNKERS"  ,
   /

We summarise the meaning of these flags below:

- ``THISFILE_DATACOLUMNS``: the number of data columns in the data file (excluding the time axis), this is required to help MAGICC pre-allocate arrays before reading
- ``THISFILE_DATAROWS`` (MAGICC7 only): the number of data rows in the data file (excluding the time axis), this is required to help MAGICC pre-allocate arrays before reading
- ``THISFILE_FIRSTYEAR``: the first year to which the data applies
- ``THISFILE_LASTYEAR``: the last year to which the data applies
- ``THISFILE_ANNUALSTEPS``: how many slices each year is divided into, i.e. ``THISFILE_ANNUALSTEPS=1`` means the data is annual, ``THISFILE_ANNUALSTEPS=12`` means that data is monthly and ``THISFILE_ANNUALSTEPS=0`` is a special convention to say that the data is given in larger than annual steps and hence must be interpolated by MAGICC internally
- ``THISFILE_FIRSTDATAROW``: the first row in which data is given, this lets MAGICC skip all the header rows in the data files
- ``THISFILE_UNITS``: the units of the data in the file, not used by MAGICC internally but provided as confirmation for the user
- ``THISFILE_DATTYPE``: indicates the type of data provided in the file, see ``pymagicc/definitions/magicc_dattype_regionmode_regions.csv``
- ``THISFILE_REGIONMODE``: indicates the regions provided in the file, see ``pymagicc/definitions/magicc_dattype_regionmode_regions.csv``

**Note**

The regional set
``["WORLD", "R5ASIA", "R5LAM", "R5REF", "R5MAF", "R5OECD", "BUNKERS"]``, which was the
standard for RCP data, is not supported by MAGICC7. Hence we provided an 'assumed
mapping' in ``pymagicc/io._InputWriter._get_data_block`` which, if we are trying to
write a ``SCEN7`` file and we are given the RCP regional set, will simply assume that
it is ok to map to the MAGICC7 regions,
``["WORLD", "R6ASIA", "R6LAM", "R6REF", "R6MAF", "R6OECD90", "BUNKERS"]`` which are
supported.
