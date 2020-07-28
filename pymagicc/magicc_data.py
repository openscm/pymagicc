from copy import deepcopy
from datetime import datetime

import numpy as np
from scmdata import ScmDataFrame

from .io import determine_tool
from .magicc_time import convert_to_datetime
from .utils import _check_file_exists


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


def _read_and_return_metadata_df(filepath):
    _check_file_exists(filepath)
    Reader = determine_tool(filepath, "reader")
    return Reader(filepath).read()


class MAGICCData(ScmDataFrame):
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
        see ``scmdata.ScmDataFrame``.

        Parameters
        ----------
        data: pd.DataFrame, pd.Series, np.ndarray or string
            A pd.DataFrame or data file, or a numpy array of timeseries data if `columns` is specified.
            If a string is passed, data will be attempted to be read from file.

        columns: dict
            Dictionary to use to write the metadata for each timeseries in data. MAGICCData will
            also attempt to infer values from data. Any values in columns will be used in
            preference to any values found in data. The default value for "model", "scenario"
            and "climate_model" is "unspecified". See ``scmdata.ScmDataFrame`` for details.

        kwargs:
            Additional parameters passed to `pyam.core.read_files` to read non-standard files.
        """
        if not isinstance(data, str):
            self.filepath = None
            self.metadata = {}
            super().__init__(data, columns=columns, **kwargs)
        else:
            filepath = data  # assume filepath
            self.filepath = filepath
            self.metadata, data, read_columns = _read_and_return_metadata_df(filepath)
            columns = deepcopy(columns) if columns is not None else {}
            for k, v in read_columns.items():
                columns.setdefault(k, v)

            columns.setdefault("model", ["unspecified"])
            columns.setdefault("scenario", ["unspecified"])
            columns.setdefault("climate_model", ["unspecified"])

            super().__init__(data, columns=columns, **kwargs)

    def _format_datetime_col(self):
        time_srs = self["time"]
        if isinstance(time_srs.iloc[0], datetime):
            pass
        elif isinstance(time_srs.iloc[0], int):
            time_srs = [datetime(y, 1, 1) for y in to_int(time_srs)]
        else:
            time_srs = time_srs.apply(lambda x: convert_to_datetime(x))

        self["time"] = time_srs

    def _raise_not_loaded_error(self):
        raise ValueError("File has not been read from disk yet")

    @property
    def is_loaded(self):
        """bool: Whether the data has been loaded yet."""
        return self._meta is not None

    def append(self, other, inplace=False, constructor_kwargs={}, **kwargs):
        """
        Append any input which can be converted to MAGICCData to self.

        Parameters
        ----------
        other : MAGICCData, pd.DataFrame, pd.Series, str
            Source of data to append.

        inplace : bool
            If True, append ``other`` inplace, otherwise return a new ``MAGICCData``
            instance.

        constructor_kwargs : dict
            Passed to ``MAGICCData`` constructor (only used if ``other`` is not a
            ``MAGICCData`` instance).

        **kwargs
            Passed to ``super().append()``
        """
        if not isinstance(other, MAGICCData):
            other = MAGICCData(other, **constructor_kwargs)

        if inplace:
            super().append(other, inplace=inplace, **kwargs)
            # updating metadata is why we can't just use ``ScmDataFrameBase``'s append
            # method
            self.metadata.update(other.metadata)
        else:
            res = super().append(other, inplace=inplace, **kwargs)
            res.metadata = deepcopy(self.metadata)
            res.metadata.update(other.metadata)

            return res

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
