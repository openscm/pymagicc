from os.path import basename, exists, join

import f90nml
import pandas as pd
from six import StringIO


class InputReader(object):
    def __init__(self, fname, lines):
        self.fname = fname
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
        :return: start, end indexs for the namelist
        """
        nml_start = None
        nml_end = None
        for i in range(len(self.lines)):
            if self.lines[i].strip().startswith('&'):
                nml_start = i

            if self.lines[i].strip().startswith('/'):
                nml_end = i
        assert nml_start is not None and nml_end is not None, \
            'Could not find namelist within {}'.format(self.fname)
        return nml_end, nml_start

    def process_metadata(self, lines):
        # TODO: replace with f90nml.reads when released
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
        :param stream: A Streamlike object (nominally StringIO) containing the
            table to be extracted
        :param metadata: Dictionary containing
        :return: Tuple of a pd.DataFrame containing the data and a Dict
            containing the units for each gas present in the output. The
            pd.DataFrame columns are named using a MultiIndex of Gas and Region
        """
        raise NotImplementedError()


class MAGICC6Reader(InputReader):
    def process_data(self, stream, metadata):
        gas = basename(self.fname).split('_')[1]
        df = pd.read_csv(
            stream,
            skip_blank_lines=True,
            delim_whitespace=True,
            index_col=0,
            engine="python")
        # Convert to a columns to a MultiIndex
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
    def process_data(self, stream, metadata):
        gases = stream.readline().split()
        assert gases[0] == 'GAS'
        gases = gases[1:]
        stream.readline()  # Unused line
        units = stream.readline().split()[1:]
        regions = stream.readline().split()[1:]
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
                raise ValueError('Different units for {} in {}'.format(v, self.fname))

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
    An interface to read (and in future write) the input files used by MAGICC.

    MAGICCInput can read input files from both MAGICC6 and MAGICC7. These
    include files with extensions .IN and .SCEN7.

    The MAGICCInput, once the target input file has been loaded it can be
     treated as a pandas DataFrame. All the methods available to a DataFrame
     can be called on the MAGICCInput.


    >>> with MAGICC6() as magicc:
    >>>     mdata = MAGICCInput('HISTRCP_CO2I_EMIS.IN')
    >>>     mdata.read(magicc.run_dir)
    >>>     mdata.plot()
    """

    def __init__(self, file_name=None):
        """
        Initialise a Input file object.

        Optionally you can specify the filename of the target file. The file is
        not read until the search directory is provided in `read`. This allows
        for MAGICCInput files to be lazy-loaded once the appropriate MAGICC run
        directory is known.
        :param file_name: Optional file name, including extension for the target
         file, i.e. 'HISTRCP_CO2I_EMIS.IN'
        """
        self.df = None
        self.metadata = {}
        self.name = file_name

    def __getitem__(self, item):
        """
        Allow for indexing like a pandas DataFrame

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

    def read(self, directory, file_name=None):
        """
        Read the Input file from disk

        :param directory: The directory to file the file from. This is often the
            run directory for a magicc instance.
        :param file_name: The filename to read. Overrides the filename provided
         in the constructor.
        """
        if file_name is not None:
            self.name = file_name
        assert self.name is not None
        fname = join(directory, self.name)
        if not exists(fname):
            raise ValueError('Cannot find {}'.format(fname))

        reader = get_reader(fname)
        self.metadata, self.df = reader.read()

    def write(self, fname):
        # TODO: Implement writing to disk
        raise NotImplementedError()
