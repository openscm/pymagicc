import re
from copy import deepcopy
from datetime import datetime
from numbers import Number
from os.path import basename

import f90nml
import numpy as np
from f90nml.namelist import Namelist
from scmdata import ScmRun

from pymagicc.errors import NoReaderWriterError
from pymagicc.magicc_time import convert_to_datetime

from .binout import _BinaryOutReader
from .compact import _BinaryCompactOutReader, _CompactOutReader
from .in_files import (
    _ConcInReader,
    _ConcInWriter,
    _HistEmisInReader,
    _HistEmisInWriter,
    _OpticalThicknessInReader,
    _OpticalThicknessInWriter,
    _RadiativeForcingInReader,
    _RadiativeForcingInWriter,
    _SurfaceTemperatureInReader,
    _SurfaceTemperatureInWriter,
)
from .mag import _MAGReader, _MAGWriter
from .out import (
    _EmisOutReader,
    _InverseEmisReader,
    _OutReader,
    _TempOceanLayersOutReader,
)
from .prn_files import _PrnReader, _PrnWriter
from .rcpdat import _RCPDatReader, _RCPDatWriter
from .scen import _ScenReader, _ScenWriter
from .scen7 import _Scen7Reader, _Scen7Writer
from .utils import _check_file_exists

UNSUPPORTED_OUT_FILES = [
    r"CARBONCYCLE.*OUT",
    r"PF\_.*OUT",
    r"DATBASKET_.*",
    r".*INVERSE\_.*EMIS.*OUT",
    r".*INVERSEEMIS\.BINOUT",
    r"PRECIPINPUT.*OUT",
    r"TEMP_OCEANLAYERS.*\.BINOUT",
    r"TIMESERIESMIX.*OUT",
    r"SUMMARY_INDICATORS.OUT",
]
"""list: List of regular expressions which define output files we cannot read.

These files are nasty to read and not that useful hence are unsupported. The solution
for these files is to fix the output format rather than hacking the readers. Obviously
that doesn't help for the released MAGICC6 binary but there is nothing we can do
there. For MAGICC7, we should have a much nicer set.

Some more details about why these files are not supported:

- ``CARBONCYCLE.OUT`` has no units and we don't want to hardcode them
- Sub annual binary files (including volcanic RF) are asking for trouble
- Permafrost output files don't make any sense right now
- Output baskets have inconsistent variable names from other outputs
- Inverse emissions files (except `INVERSEEMIS.OUT`) have no units and we don't want
  to hardcode them
- We have no idea what the precipitation input is
- Temp ocean layers is hard to predict because it has many layers
- Time series mix output files don't have units or regions
- Summary indicator files are a brand new format for little gain
"""


def _unsupported_file(filepath):
    for outfile in UNSUPPORTED_OUT_FILES:
        if re.match(outfile, filepath):
            return True

    return False


def determine_tool(filepath, tool_to_get):
    """
    Determine the tool to use for reading/writing.

    The function uses an internally defined set of mappings between filepaths,
    regular expresions and readers/writers to work out which tool to use
    for a given task, given the filepath.

    It is intended for internal use only, but is public because of its
    importance to the input/output of pymagicc.

    If it fails, it will give clear error messages about why and what the
    available regular expressions are.

    .. code:: python

        >>> mdata = MAGICCData()
        >>> mdata.read(MAGICC7_DIR, HISTRCP_CO2I_EMIS.txt)
        ValueError: Couldn't find appropriate writer for HISTRCP_CO2I_EMIS.txt.
        The file must be one of the following types and the filepath must match its corresponding regular expression:
        SCEN: ^.*\\.SCEN$
        SCEN7: ^.*\\.SCEN7$
        prn: ^.*\\.prn$

    Parameters
    ----------
    filepath : str
        Name of the file to read/write, including extension

    tool_to_get : str_check_file_exists
        The tool to get, valid options are "reader", "writer".
        Invalid values will throw a NoReaderWriterError.
    """
    file_regexp_reader_writer = {
        "SCEN": {"regexp": r"^.*\.SCEN$", "reader": _ScenReader, "writer": _ScenWriter},
        "SCEN7": {
            "regexp": r"^.*\.SCEN7$",
            "reader": _Scen7Reader,
            "writer": _Scen7Writer,
        },
        "prn": {"regexp": r"^.*\.prn$", "reader": _PrnReader, "writer": _PrnWriter},
        # "Sector": {"regexp": r".*\.SECTOR$", "reader": _Scen7Reader, "writer": _Scen7Writer},
        "EmisIn": {
            "regexp": r"^.*\_EMIS.*\.IN$",
            "reader": _HistEmisInReader,
            "writer": _HistEmisInWriter,
        },
        "ConcIn": {
            "regexp": r"^.*\_CONC.*\.IN$",
            "reader": _ConcInReader,
            "writer": _ConcInWriter,
        },
        "OpticalThicknessIn": {
            "regexp": r"^.*\_OT\.IN$",
            "reader": _OpticalThicknessInReader,
            "writer": _OpticalThicknessInWriter,
        },
        "RadiativeForcingIn": {
            "regexp": r"^.*\_RF\.(IN|MON)$",
            "reader": _RadiativeForcingInReader,
            "writer": _RadiativeForcingInWriter,
        },
        "SurfaceTemperatureIn": {
            "regexp": r"^.*SURFACE\_TEMP\.(IN|MON)$",
            "reader": _SurfaceTemperatureInReader,
            "writer": _SurfaceTemperatureInWriter,
        },
        "Out": {
            "regexp": r"^DAT\_.*(?<!EMIS)\.OUT$",
            "reader": _OutReader,
            "writer": None,
        },
        "EmisOut": {
            "regexp": r"^DAT\_.*EMIS\.OUT$",
            "reader": _EmisOutReader,
            "writer": None,
        },
        "InverseEmis": {
            "regexp": r"^INVERSEEMIS\.OUT$",
            "reader": _InverseEmisReader,
            "writer": None,
        },
        "TempOceanLayersOut": {
            "regexp": r"^TEMP\_OCEANLAYERS.*\.OUT$",
            "reader": _TempOceanLayersOutReader,
            "writer": None,
        },
        "BinOut": {
            "regexp": r"^DAT\_.*\.BINOUT$",
            "reader": _BinaryOutReader,
            "writer": None,
        },
        "RCPData": {
            "regexp": r"^.*\.DAT",
            "reader": _RCPDatReader,
            "writer": _RCPDatWriter,
        },
        "CompactOut": {
            "regexp": r"^.*COMPACT\.OUT$",
            "reader": _CompactOutReader,
            "writer": None,
        },
        "CompactBinOut": {
            "regexp": r"^.*COMPACT\.BINOUT$",
            "reader": _BinaryCompactOutReader,
            "writer": None,
        },
        "MAG": {"regexp": r"^.*\.MAG", "reader": _MAGReader, "writer": _MAGWriter},
        # "InverseEmisOut": {"regexp": r"^INVERSEEMIS\_.*\.OUT$", "reader": _Scen7Reader, "writer": _Scen7Writer},
    }

    fbase = basename(filepath)
    if _unsupported_file(fbase):
        raise NoReaderWriterError(
            "{} is in an odd format for which we will never provide a reader/writer.".format(
                filepath
            )
        )

    for file_type, file_tools in file_regexp_reader_writer.items():
        if re.match(file_tools["regexp"], fbase):
            try:
                tool = file_tools[tool_to_get]
                if tool is None:
                    error_msg = "A {} for `{}` files is not yet implemented".format(
                        tool_to_get, file_tools["regexp"]
                    )
                    raise NotImplementedError(error_msg)

                return tool

            except KeyError:
                valid_tools = [k for k in file_tools.keys() if k != "regexp"]
                error_msg = (
                    "MAGICCData does not know how to get a {}, "
                    "valid options are: {}".format(tool_to_get, valid_tools)
                )
                raise KeyError(error_msg)

    para_file = "PARAMETERS.OUT"
    if (filepath.endswith(".CFG")) and (tool_to_get == "reader"):
        error_msg = (
            "MAGCCInput cannot read .CFG files like {}, please use "
            "pymagicc.io.read_cfg_file".format(filepath)
        )

    elif (filepath.endswith(para_file)) and (tool_to_get == "reader"):
        error_msg = (
            "MAGCCInput cannot read PARAMETERS.OUT as it is a config "
            "style file, please use pymagicc.io.read_cfg_file"
        )

    else:
        regexp_list_str = "\n".join(
            [
                "{}: {}".format(k, v["regexp"])
                for k, v in file_regexp_reader_writer.items()
            ]
        )
        error_msg = (
            "Couldn't find appropriate {} for {}.\nThe file must be one "
            "of the following types and the filepath must match its "
            "corresponding regular "
            "expression:\n{}".format(tool_to_get, fbase, regexp_list_str)
        )

    raise NoReaderWriterError(error_msg)


def _read_metadata_and_df(filepath):
    from pymagicc.io import determine_tool

    _check_file_exists(filepath)
    Reader = determine_tool(filepath, "reader")
    return Reader(filepath).read()


def read_mag_file_metadata(filepath):
    """
    Read only the metadata in a ``.MAG`` file

    This provides a way to access a ``.MAG`` file's metadata without reading the
    entire datablock, significantly reducing read time.

    Parameters
    ----------
    filepath : str
        Full path (path and name) to the file to read

    Returns
    -------
    dict
        Metadata read from the file

    Raises
    ------
    ValueError
        The file is not a ``.MAG`` file
    """
    if not filepath.endswith(".MAG"):
        raise ValueError("File must be a `.MAG` file")

    reader = _MAGReader(filepath)
    nml_start, nml_end = reader._set_lines_and_find_nml(metadata_only=True)

    return reader._derive_metadata(nml_start, nml_end)


def read_cfg_file(filepath):
    """
    Read a MAGICC ``.CFG`` file, or any other Fortran namelist

    Parameters
    ----------
    filepath : str
        Full path (path and name) to the file to read

    Returns
    -------
    :obj:`f90nml.Namelist`
        An `f90nml <https://github.com/marshallward/f90nml>`_ ``Namelist`` instance
        which contains the namelists in the file. A ``Namelist`` can be accessed just
        like a dictionary.
    """
    _check_file_exists(filepath)
    return f90nml.read(filepath)


def pull_cfg_from_parameters_out(parameters_out, namelist_to_read="nml_allcfgs"):
    """
    Pull out a single config set from a parameters_out namelist.

    This function returns a single file with the config that needs to be passed to
    MAGICC in order to do the same run as is represented by the values in
    ``parameters_out``.

    Parameters
    ----------
    parameters_out : dict, f90nml.Namelist
        The parameters to dump

    namelist_to_read : str
        The namelist to read from the file.

    Returns
    -------
    :obj:`f90nml.Namelist`
        An f90nml object with the cleaned, read out config.

    Examples
    --------
    >>> cfg = pull_cfg_from_parameters_out(magicc.metadata["parameters"])
    >>> cfg.write("/somewhere/else/ANOTHERNAME.cfg")
    """
    single_cfg = Namelist({namelist_to_read: {}})
    for key, value in parameters_out[namelist_to_read].items():
        if "file_tuning" in key:
            single_cfg[namelist_to_read][key] = ""
        else:
            try:
                if isinstance(value, str):
                    single_cfg[namelist_to_read][key] = value.strip(" \t\n\r").replace(
                        "\x00", ""
                    )
                elif isinstance(value, list):
                    clean_list = [v.strip(" \t\n\r").replace("\x00", "") for v in value]
                    single_cfg[namelist_to_read][key] = [v for v in clean_list if v]
                else:
                    if not isinstance(value, Number):
                        raise AssertionError("value is not a number: {}".format(value))

                    single_cfg[namelist_to_read][key] = value
            except AttributeError:
                if isinstance(value, list):
                    if not all([isinstance(v, Number) for v in value]):
                        raise AssertionError(
                            "List where not all values are numbers? " "{}".format(value)
                        )

                    single_cfg[namelist_to_read][key] = value
                else:
                    raise AssertionError(
                        "Unexpected cause in out parameters conversion"
                    )

    return single_cfg


def pull_cfg_from_parameters_out_file(
    parameters_out_file, namelist_to_read="nml_allcfgs"
):
    """
    Pull out a single config set from a MAGICC ``PARAMETERS.OUT`` file.

    This function reads in the ``PARAMETERS.OUT`` file and returns a single file with
    the config that needs to be passed to MAGICC in order to do the same run as is
    represented by the values in ``PARAMETERS.OUT``.

    Parameters
    ----------
    parameters_out_file : str
        The ``PARAMETERS.OUT`` file to read

    namelist_to_read : str
        The namelist to read from the file.

    Returns
    -------
    :obj:`f90nml.Namelist`
        An f90nml object with the cleaned, read out config.

    Examples
    --------
    >>> cfg = pull_cfg_from_parameters_out_file("PARAMETERS.OUT")
    >>> cfg.write("/somewhere/else/ANOTHERNAME.cfg")
    """
    parameters_out = read_cfg_file(parameters_out_file)
    return pull_cfg_from_parameters_out(
        parameters_out, namelist_to_read=namelist_to_read
    )


def get_generic_rcp_name(inname):
    """
    Convert an RCP name into the generic Pymagicc RCP name

    The conversion is case insensitive.

    Parameters
    ----------
    inname : str
        The name for which to get the generic Pymagicc RCP name

    Returns
    -------
    str
        The generic Pymagicc RCP name

    Examples
    --------
    >>> get_generic_rcp_name("RCP3PD")
    "rcp26"
    """
    # TODO: move into OpenSCM
    mapping = {
        "rcp26": "rcp26",
        "rcp3pd": "rcp26",
        "rcp45": "rcp45",
        "rcp6": "rcp60",
        "rcp60": "rcp60",
        "rcp85": "rcp85",
    }
    try:
        return mapping[inname.lower()]
    except KeyError:
        error_msg = "No generic name for input: {}".format(inname)
        raise ValueError(error_msg)


def to_int(x):
    """
    Convert inputs to int and check conversion is sensible

    Parameters
    ----------
    x : :obj:`np.array`
        Values to convert

    Returns
    -------
    :obj:`np.array` of :obj:`int`
        Input, converted to int

    Raises
    ------
    ValueError
        If the int representation of any of the values is not equal to its original
        representation (where equality is checked using the ``!=`` operator).

    TypeError
        x is not a ``np.ndarray``
    """
    if not isinstance(x, np.ndarray):
        raise TypeError(
            "For our own sanity, this method only works with np.ndarray input. "
            "x is type: {}".format(type(x))
        )
    cols = np.array([int(v) for v in x])
    invalid_vals = x[cols != x]
    if invalid_vals.size:
        raise ValueError("invalid values `{}`".format(list(invalid_vals)))

    return cols


class MAGICCData(ScmRun):
    """
    An interface to read and write the input files used by MAGICC.

    MAGICCData can read input files from both MAGICC6 and MAGICC7. It returns
    files in a common format with a common vocabulary to simplify the process
    of reading, writing and handling MAGICC data. For more information on file
    conventions, see :ref:`magicc_file_conventions`.

    See ``notebooks/Input-Examples.ipynb`` for usage examples.

    Attributes
    ----------
    data : :obj:`pd.DataFrame`
        A pandas dataframe with the data.

    metadata : dict
        Metadata for the data in ``self.df``.

    filepath : str
        The file the data was loaded from. None if data was not loaded from a file.
    """

    def __init__(self, data, columns=None, **kwargs):
        """
        Initialise a MAGICCData instance

        Here we provide a brief over of inputs, for more details
        see :class:`scmdata.ScmRun`.

        Parameters
        ----------
        data: pd.DataFrame, pd.Series, np.ndarray or string
            A pd.DataFrame or data file, or a numpy array of timeseries data if `columns` is specified.
            If a string is passed, data will be attempted to be read from file.

        columns: dict
            Dictionary to use to write the metadata for each timeseries in data. MAGICCData will
            also attempt to infer values from data. Any values in columns will be used in
            preference to any values found in data. The default value for "model", "scenario"
            and "climate_model" is "unspecified". See :class:`scmdata.ScmRun` for details.

        kwargs:
            Additional parameters passed to `pyam.core.read_files` to read non-standard files.
        """
        if not isinstance(data, str):
            self.filepath = None
            super().__init__(data, columns=columns, **kwargs)
        else:

            filepath = data  # assume filepath
            self.filepath = filepath
            metadata, data, read_columns = _read_metadata_and_df(filepath)
            data.columns = range(len(data.columns))
            columns = deepcopy(columns) if columns is not None else {}
            for k, v in read_columns.items():
                columns.setdefault(k, v)

            columns.setdefault("model", ["unspecified"])
            columns.setdefault("scenario", ["unspecified"])
            columns.setdefault("climate_model", ["unspecified"])

            super().__init__(data, columns=columns, **kwargs)
            self.metadata = metadata

    def _format_datetime_col(self):
        time_srs = self["time"]
        if isinstance(time_srs.iloc[0], datetime):
            pass
        elif isinstance(time_srs.iloc[0], int):
            time_srs = [datetime(y, 1, 1) for y in to_int(time_srs)]
        else:
            time_srs = time_srs.apply(lambda x: convert_to_datetime(x))

        self["time"] = time_srs

    def write(self, filepath, magicc_version):
        """
        Write an input file to disk.

        For more information on file conventions, see :ref:`magicc_file_conventions`.

        Parameters
        ----------
        filepath : str
            Filepath of the file to write.

        magicc_version : int
            The MAGICC version for which we want to write files. MAGICC7 and MAGICC6
            namelists are incompatible hence we need to know which one we're writing
            for.
        """
        writer = determine_tool(filepath, "writer")(magicc_version=magicc_version)
        writer.write(self, filepath)
