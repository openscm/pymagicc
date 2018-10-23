MAGICC file conventions
=======================

Input files

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
