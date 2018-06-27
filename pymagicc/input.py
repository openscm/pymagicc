from os.path import basename, exists, join

import f90nml
import pandas as pd
from io import StringIO
from pymagicc import MAGICC6


class InputReader(object):
    def __init__(self, filename, lines):
        self.filename = filename
        self.lines = lines

    def read(self):
        nml_end, nml_start = self._find_nml()

        metadata = self.process_metadata(self.lines[nml_start:nml_end + 1])
        metadata['header'] = "".join(self.lines[:nml_start])

        # Create a stream from the remaining lines, ignoring any blank lines
        stream = StringIO()
        cleaned_lines = [l.strip()
                         for l in self.lines[nml_end + 1:] if l.strip()]
        stream.write("\n".join(cleaned_lines))
        stream.seek(0)

        df, units = self.process_data(stream, metadata)
        metadata['units'] = units
        return metadata, df

    def _find_nml(self):
        """
        Find the start and end of the embedded namelist

        # Returns
        start, end (int): indexes for the namelist
        """
        nml_start = None
        nml_end = None
        for i in range(len(self.lines)):
            if self.lines[i].strip().startswith('&'):
                nml_start = i

            if self.lines[i].strip().startswith('/'):
                nml_end = i
        assert nml_start is not None and nml_end is not None, \
            'Could not find namelist within {}'.format(self.filename)
        return nml_end, nml_start

    def process_metadata(self, lines):
        # TODO: replace with f90nml.reads when released (>1.0.2)
        parser = f90nml.Parser()
        nml = parser._readstream(lines, {})
        metadata = {
            k.split('_')[1]: nml['THISFILE_SPECIFICATIONS'][k]
            for k in nml['THISFILE_SPECIFICATIONS']
        }

        return metadata

    def process_data(self, stream, metadata):
        """
        Extract the tabulated data from a subset of the input file

        # Arguments
        stream (Streamlike object): A Streamlike object (nominally StringIO)
            containing the table to be extracted
        metadata (Dict): Dictionary containing

        # Returns
        *To be updated when stable*
        return (Tuple): Tuple of a pd.DataFrame containing the data and a Dict
            containing the metadata. The pd.DataFrame columns are named using
            a MultiIndex
        """
        raise NotImplementedError()


class MAGICC6Reader(InputReader):
    def process_data(self, stream, metadata):
        gas = basename(self.filename).split('_')[1]
        df = pd.read_csv(
            stream,
            skip_blank_lines=True,
            delim_whitespace=True,
            index_col=0,
            engine="python")
        # Convert columns to a MultiIndex
        df.columns = [
            [gas] * len(df.columns),
            df.columns
        ]
        df.index.name = 'YEAR'

        units = {
            gas: metadata['units']
        }
        return df, units


class MAGICC7Reader(InputReader):
    def _read_line(self, stream, expected_header):
        tokens = stream.readline().split()
        assert tokens[0] == expected_header
        return tokens[1:]

    def process_data(self, stream, metadata):
        gases = self._read_line(stream, 'GAS')
        self._read_line(stream, 'TODO')
        units = self._read_line(stream, 'UNITS')
        regions = self._read_line(stream, 'YEARS')  # Note that regions line starts with 'YEARS' instead of 'REGIONS'
        index = pd.MultiIndex.from_arrays([gases, regions], names=['GAS', 'REGION'])
        df = pd.read_csv(
            stream,
            skip_blank_lines=True,
            delim_whitespace=True,
            names=None,
            header=None,
            index_col=0)
        df.index.name = 'YEAR'
        df.columns = index

        return df, self._extract_units(gases, units)

    def _extract_units(self, gases, units):
        combos = set(zip(gases, units))
        result = {}
        for v, u in combos:
            if v not in result:
                result[v] = u
            else:
                # this isn't expected to happen, but should check anyway
                raise ValueError('Different units for {} in {}'.format(v, self.filename))

        return result


_file_types = {
    'MAGICC6': MAGICC6Reader,
    'MAGICC7': MAGICC7Reader,
}


def get_reader(fname):
    with open(fname) as f:
        lines = f.readlines()

    # Infer the file type from the header
    if '.__  __          _____ _____ _____ _____   ______   ______ __  __ _____  _____  _____ _   _' \
            in lines[0]:
        file_type = 'MAGICC7'
    else:
        file_type = 'MAGICC6'

    return _file_types[file_type](fname, lines)


class MAGICCInput(object):
    """
    *Warning: API likely to change*

    An interface to (in future) read and write the input files used by MAGICC.

    MAGICCInput can read input files from both MAGICC6 and MAGICC7. It returns
    files in a common format with a common vocabulary to simplify the process
    of reading, writing and handling MAGICC data.

    The MAGICCInput, once the target input file has been loaded, can be
    treated as a Pandas DataFrame. All the methods available to a DataFrame
    can be called on the MAGICCInput.

    ```python
    with MAGICC6() as magicc:
        mdata = MAGICCInput('HISTRCP_CO2I_EMIS.IN')
        mdata.read(magicc.run_dir)
        mdata.plot()
    ```

    # Parameters
    filename (str): Name of the file to read
    """

    def __init__(self, filename=None):
        """
        Initialise an Input file object.

        Optionally you can specify the filename of the target file. The file is
        not read until the search directory is provided in `read`. This allows
        for MAGICCInput files to be lazy-loaded once the appropriate MAGICC run
        directory is known.
        :param filename: Optional file name, including extension for the target
         file, i.e. 'HISTRCP_CO2I_EMIS.IN'
        """
        self.df = None
        self.metadata = {}
        self.name = filename

    def __getitem__(self, item):
        """
        Allow for indexing like a Pandas DataFrame

        >>> inpt = MAGICCInput('HISTRCP_CO2_CONC.IN')
        >>> inpt.read('./')
        >>> assert (inpt['CO2']['GLOBAL'] == inpt.df['CO2']['GLOBAL']).all()
        """
        if not self.is_loaded:
            raise ValueError('File has not been read from disk yet')
        return self.df[item]

    def __getattr__(self, item):
        """
        Proxy any attributes/functions on the dataframe
        """
        if not self.is_loaded:
            raise ValueError('File has not been read from disk yet')
        return getattr(self.df, item)

    @property
    def is_loaded(self):
        return self.df is not None

    def read(self, filepath=None, filename=None):
        """
        *Warning: still under construction*

        Read an input file from disk

        # Parameters
        filepath (str): The directory to file the file from. This is often the
            run directory for a magicc instance. If None is passed,
            the run directory for the bundled version of MAGICC6 is used.
        filename (str): The filename to read. Overrides any existing values.
        """
        if filepath is None:
            filepath = MAGICC6().original_dir
        if filename is not None:
            self.name = filename
        assert self.name is not None
        filename = join(filepath, self.name)
        if not exists(filename):
            raise ValueError('Cannot find {}'.format(filename))

        reader = get_reader(filename)
        self.metadata, self.df = reader.read()

    def write(self, filename):
        """
        TODO: Implement writing to disk
        """
        raise NotImplementedError()
