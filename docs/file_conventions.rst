.. _magicc_file_conventions:

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
followed as we are yet to set up tests for running MAGICC with *all* of
these different files after they’ve been set using Pymagicc).

#. Files ending in ``.SCEN7`` and ``.IN`` are input files. They
   are both the same format: some notes, then the data in space
   separated columns.

   #. Files ending in ``.SCEN7`` are scenario input files.
   #. Files ending in ``.IN`` are input files, typically related to the
      historical period. The filename indicates what data is in the file
      e.g. ``CONC.IN`` indicates that this file contains concentrations.

#. Files ending in ``.CFG`` are config files. They are used to set
   MAGICC’s configuration and are always in the format of a FORTRAN90
   namelist.
#. Files ending in ``.SCEN`` are emissions scenario files. These files are a legacy
   format. They are used to drive MAGICC6 and can also be used to drive MAGICC7, although the results are much less predictable with MAGICC7.

   - ``.SCEN`` files have to be written very carefully, in particular their metadata.
     Specifically, when a ``.SCEN`` file is written, ``writer.metadata["description"]``
     is written in the fourth line of the file, ``writer.metadata["notes"]`` is
     written in the fifth line of the file and all other metadata is written at the
     end of the file. If ``description``/``notes`` is not available in
     ``writer.metadata`` then these lines are automatically filled by Pymagicc.
   - When ``.SCEN`` files are read, their ``scenario`` metadata is automatically
     filled from the third line of the input file (similarly, ``scenario`` is also
     written to the third line of the file when writing ``.SCEN`` files).

#. Files ending in ``.prn`` are emissions input files for ozone
   depleting substances. This file format is comprised of a header row
   which contains (unlabelled) information about the first data row,
   start year and end year, then some notes rows, then the data in fixed
   width columns. This file format is used by MAGICC6 but has been
   deprecated for MAGICC7 in favour of ``*EMIS.IN`` and ``*.SCEN7``
   files.

Column meaning
++++++++++++++

In MAGICC data and input files there are a number of columns, each of which is explained here.

- variable: the variable for which the data applies

- region: the region in which the data applies

- units: the units of the data

- time: the point in time at which the data occurs

    - note that the internal convention is that state variables are start of time period values (e.g. 1st January 1990) whilst fluxes are time period averages/middle of time period values

- set: a MAGICC flag which defines what MAGICC should do with the data in the timeseries

    - SET: set the given variable in the given region to the value provided (standard setting)
    - ADD: add the data for the given variable in the given region to any already read in data for that variable in that region (although it is not clear to the authors of Pymagicc how exactly to use this flag)
    - SUBTRACT: subtract the data for the given variable in the given region from any already read in data for that variable in that region (although it is not clear to the authors of Pymagicc how exactly to use this flag)

Column ordering and spacing
+++++++++++++++++++++++++++

For some of MAGICC's input files, the column ordering and spacing is crucially important.
For these files, if the columns are out of order or a single character too long/short, MAGICC will not read the data correctly and the run will be erroneous.

We check that ``pymagicc.io`` writes files with the correct column order and spacing with ``tests/test_io.py::test_writing_spacing_column_order``.
In these tests, we check against pre-written files.
The files we use as verification can differ from the files in ``pymagicc/MAGICC6/run`` for a number of reasons, which we summarise here.

- ``.prn`` files

    - data block header not read by MAGICC so not worried about differences
    - first number tells MAGICC how many lines to skip to get to data block so we can remove the line between the data block header and the data block which appears in the original files
    - the header is different from the original files because the original files have spurious lines of notes at the end (we do not attempt to write a reader which can handle this very confusing edge case)

- ``.SCEN`` files

    - variable names aren't read so making them match original files
      isn't a priority

- ``HIST*.IN`` files

    - column width doesn't matter as MAGICC looks for a whitespace delimiter when reading in these files, hence differences from originals are ok


Namelists
---------

At the top of each input file there is a namelist called ``thisfile_specifications``. It looks something like this

.. code:: Fortran

   &THISFILE_SPECIFICATIONS
    THISFILE_DATACOLUMNS     =    7  ,
    THISFILE_DATAROWS        =  266  ,
    THISFILE_FIRSTYEAR       = 1750  ,
    THISFILE_LASTYEAR        = 2015  ,
    THISFILE_ANNUALSTEPS     =    1  ,
    THISFILE_FIRSTDATAROW    =   99  ,
    THISFILE_UNITS           = "kt"  ,
    THISFILE_DATTYPE         = "REGIONDATA"  ,
    THISFILE_REGIONMODE      = "RCPPLUSBUNKERS"  ,
    THISFILE_TIMESERIESTYPE  = "MONTHLY"  ,
   /

We summarise the meaning of these flags below:

- ``THISFILE_DATACOLUMNS``: the number of data columns in the data file (excluding the time axis), this is required to help MAGICC pre-allocate arrays before reading
- ``THISFILE_DATAROWS`` (MAGICC7 only): the number of data rows in the data file (excluding the time axis), this is required to help MAGICC pre-allocate arrays before reading
- ``THISFILE_FIRSTYEAR``: the first year to which the data applies
- ``THISFILE_LASTYEAR``: the last year to which the data applies
- ``THISFILE_ANNUALSTEPS``: how many slices each year is divided into, i.e. ``THISFILE_ANNUALSTEPS=1`` means the data is annual, ``THISFILE_ANNUALSTEPS=12`` means that data is monthly and ``THISFILE_ANNUALSTEPS=0`` is a special convention to say that the data is given in irregular or larger than annual steps and hence must be interpolated by MAGICC internally
- ``THISFILE_FIRSTDATAROW``: the first row in which data is given, this lets MAGICC skip all the header rows in the data files
- ``THISFILE_UNITS``: the units of the data in the file, not used by MAGICC internally but provided as confirmation for the user
- ``THISFILE_DATTYPE``: indicates the type of data provided in the file, see ``pymagicc/definitions/magicc_dattype_regionmode_regions.csv``
- ``THISFILE_REGIONMODE``: indicates the regions provided in the file, see ``pymagicc/definitions/magicc_dattype_regionmode_regions.csv``. ``NONE`` is written if the supplied regions are not compatible with any of MAGICC's internal REGIONMODE flags.
- ``THISFILE_TIMESERIESTYPE``: indicates the type of the timeseries provided in the file. Note that this flag is only used by ``.MAG`` files at the moment (we hope to add it to MAGICC7 input and output in future). Available options: ``MONTHLY`` (monthly mean values), ``POINT_START_YEAR`` (start of year values), ``POINT_MID_YEAR`` (middle of year values), ``POINT_END_YEAR`` (end of year values), ``AVERAGE_YEAR_START_YEAR`` (average over a year, centred on Jan 1 of the stated year i.e. uses data from July of the previous year until June of the year), ``AVERAGE_YEAR_MID_YEAR`` (average over a year only using the monthly averages of the months in the specified year), ``AVERAGE_YEAR_END_YEAR`` (average over a year, centred on December 31 of the stated year i.e. uses data from July of year until June of next year).

**Note**

The regional set
``["WORLD", "R5ASIA", "R5LAM", "R5REF", "R5MAF", "R5OECD", "BUNKERS"]``, which was the
standard for RCP data, is not supported by MAGICC7. Hence we provided an 'assumed
mapping' in ``pymagicc/io._InputWriter._get_data_block`` which, if we are trying to
write a ``SCEN7`` file and we are given the RCP regional set, will simply assume that
it is ok to map to the MAGICC7 regions,
``["WORLD", "R5.2ASIA", "R5.2LAM", "R5.2REF", "R5.2MAF", "R5.2OECD", "BUNKERS"]``, which are supported.


The Future
----------

In future, the MAGICC developers are aiming to move all of MAGICC's input and output
to the ``.MAG`` format. A marked up sample file can be found in ``tests/test_data``.
Pymagicc supports reading and writing these files but they are currently not used to
actually run MAGICC anywhere.

To supplement the sample file, we also provide the following overview of the format.

The first section of the file is a header, for storing whatever text the user wants.
This section must always start with ``---- HEADER ----``. The section is ignored by
MAGICC but can be used by other readers and writers.

The next section is other metadata, in ``"key: value"`` pairs. As a result, each key
and value can only be stored and read as strings. This section must always start with
```---- METADATA ----```. The second section allows for storage of metadata, like the
global attributes section in a netcdf file. This section is also ignored by MAGICC.

The third section is a Fortran namelist, which stores the flags required for MAGICC to
be able to read the file. The flags must match the flags used by MAGICC internally
(see `Namelists`_). In Pymagicc, these flags are written automatically, the user cannot
write them.

The fourth section is the data. This is always a data block with four header rows:
variable, todo, units, region (see `Column meaning`_). In the data block, the first
column is the time axis and the subsequent columns are the timeseries.

This format is highly custom and specialised for use with MAGICC, with the secondary
characteristic of being somewhat human readable. Having said this, if you want to work
with the data, we strongly recommend using Pymagicc's io module (:ref:`pymagicc.io`) to
allow easy conversion to more familiar Python types such as dictionaries, lists,
strings and most importantly pandas data frames.
