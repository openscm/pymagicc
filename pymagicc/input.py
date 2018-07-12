from os.path import basename, exists, join, splitext
from shutil import copyfileobj

import f90nml
from f90nml.namelist import Namelist
import pandas as pd
import re
from six import StringIO

from pymagicc import MAGICC6


class InputReader(object):
    header_tags = [
        "compiled by",
        "contact",
        "data",
        "date",
        "description",
        "gas",
        "source",
        "unit",
    ]

    def __init__(self, filename):
        self.filename = filename

    def _set_lines(self):
        with open(self.filename, "r") as f:
            self.lines = f.readlines()

    def read(self):
        self._set_lines()
        # refactor to:
        # header, nml, data = self._get_split_lines()
        # metadata = self.process_metadata(header, nml)
        # df = self.process_data(data, metadata)
        # return metadata, df

        nml_end, nml_start = self._find_nml()

        nml_values = self.process_metadata(self.lines[nml_start : nml_end + 1])
        metadata = {key: value for key, value in nml_values.items() if key == "units"}
        metadata["header"] = "".join(self.lines[:nml_start])
        header_metadata = self.process_header(metadata["header"])
        metadata.update(header_metadata)

        # Create a stream from the remaining lines, ignoring any blank lines
        stream = StringIO()
        cleaned_lines = [l.strip() for l in self.lines[nml_end + 1 :] if l.strip()]
        stream.write("\n".join(cleaned_lines))
        stream.seek(0)

        df, metadata = self.process_data(stream, metadata)

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
            if self.lines[i].strip().startswith("&"):
                nml_start = i

            if self.lines[i].strip().startswith("/"):
                nml_end = i
        assert (
            nml_start is not None and nml_end is not None
        ), "Could not find namelist within {}".format(
            self.filename
        )
        return nml_end, nml_start

    def process_metadata(self, lines):
        # TODO: replace with f90nml.reads when released (>1.0.2)
        parser = f90nml.Parser()
        nml = parser._readstream(lines, {})
        metadata = {
            k.split("_")[1]: nml["THISFILE_SPECIFICATIONS"][k]
            for k in nml["THISFILE_SPECIFICATIONS"]
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
        return (Tuple): Tuple of a pd.DataFrame containing the data and a Dict
            containing the metadata. The pd.DataFrame columns are named using
            a MultiIndex
        """
        raise NotImplementedError()

    def process_header(self, header):
        """
        Parse the header for additional metadata

        The metadata is only present in MAGICC7 input files.
        :param header: A string containing all the lines in the header
        :return: A dict containing the addtional metadata in the header
        """
        metadata = {}
        for l in header.split("\n"):
            l = l.strip()
            for tag in self.header_tags:
                tag_text = "{}:".format(tag)
                if l.lower().startswith(tag_text):
                    metadata[tag] = l[len(tag_text) + 1 :].strip()
        return metadata

    def _read_data_header_line(self, stream, expected_header):
        tokens = stream.readline().split()
        assert tokens[0] == expected_header
        return tokens[1:]


class MAGICC6Reader(InputReader):
    def process_data(self, stream, metadata):
        df = pd.read_csv(
            stream, skip_blank_lines=True, delim_whitespace=True, engine="python"
        )

        df.rename(columns={"COLCODE": "YEAR"}, inplace=True)

        df = pd.melt(df, id_vars="YEAR", var_name="REGION")

        df["UNITS"] = metadata["units"]
        metadata.pop("units")

        df["TODO"] = "SET"

        filename_only = splitext(basename(self.filename))[0]
        df["VARIABLE"] = "_".join(filename_only.split("_")[1:])

        df.set_index(["VARIABLE", "TODO", "REGION", "YEAR", "UNITS"], inplace=True)

        return df, metadata


class MAGICC7Reader(InputReader):
    def process_data(self, stream, metadata):
        variables = self._read_data_header_line(stream, "GAS")
        todo = self._read_data_header_line(stream, "TODO")
        units = self._read_data_header_line(stream, "UNITS")
        regions = self._read_data_header_line(
            stream, "YEARS"
        )  # Note that regions line starts with 'YEARS' instead of 'REGIONS'
        index = pd.MultiIndex.from_arrays(
            [variables, todo, regions, units],
            names=["VARIABLE", "TODO", "REGION", "UNITS"],
        )
        df = pd.read_csv(
            stream,
            skip_blank_lines=True,
            delim_whitespace=True,
            names=None,
            header=None,
            index_col=0,
        )
        df.index.name = "YEAR"
        df.columns = index
        df = df.T.stack()

        return df, metadata

    def _extract_units(self, gases, units):
        combos = set(zip(gases, units))
        result = {}
        for v, u in combos:
            if v not in result:
                result[v] = u
            else:
                # this isn't expected to happen, but should check anyway
                raise ValueError(
                    "Different units for {} in {}".format(v, self.filename)
                )

        return result


class HIST_CONC_INReader(InputReader):
    def process_data(self, stream, metadata):
        regions = self._read_data_header_line(
            stream, "COLCODE"
        )  # Note that regions line starts with 'COLCODE' instead of 'REGIONS'
        units = [metadata["units"]] * len(regions)
        metadata.pop("units")
        todo = ["SET"] * len(regions)
        variables = [self._get_variable_from_filename()] * len(regions)
        index = pd.MultiIndex.from_arrays(
            [variables, todo, regions, units],
            names=["VARIABLE", "TODO", "REGION", "UNITS"],
        )
        df = pd.read_csv(
            stream,
            skip_blank_lines=True,
            delim_whitespace=True,
            names=None,
            header=None,
            index_col=0,
        )
        df.index.name = "YEAR"
        df.columns = index
        df = df.T.stack()

        return df, metadata

    def _get_variable_from_filename(self):
        regexp_capture_variable = re.compile(r".*\_(\w*\_CONC)\.IN$")
        try:
            return regexp_capture_variable.search(self.filename).group(1)
        except AttributeError:
            error_msg = "Cannot determine variable from filename: {}".format(
                self.filename
            )
            raise SyntaxError(error_msg)


class HIST_EMIS_INReader(InputReader):
    # TODO: fix this. Not high priority now
    def process_data(self, stream, metadata):
        if any(["COLCODE" in line for line in self.lines]):
            proxy_reader = MAGICC6Reader(self.filename)
        else:
            proxy_reader = MAGICC7Reader(self.filename)
        return proxy_reader.process_data(stream, metadata)


class InputWriter(object):
    def __init__(self):
        pass

    def write(self, magicc_input, filename, filepath=None):
        """
        Write a MAGICC input file from df and metadata

        # Arguments
        filename (str): name of file to write to
        filepath (str): path in which to write file. If not provided,
           the file will be written in the current directory (TODO: check this is true...)
        """
        self.minput = magicc_input

        if filepath is not None:
            filename = join(filepath, filename)

        output = StringIO()
        output.write(self._get_header())

        nml, data_block = self._get_nml_and_data_block()

        no_lines_nml_header_end = 2  # &NML_INDICATOR goes above, / goes at end
        line_after_nml = "\n"

        nml["THISFILE_SPECIFICATIONS"]["THISFILE_FIRSTDATAROW"] = 0
        nml["THISFILE_SPECIFICATIONS"]["THISFILE_FIRSTDATAROW"] = (
            len(output.getvalue().split("\n"))
            + len(nml["THISFILE_SPECIFICATIONS"])
            + no_lines_nml_header_end
            + len(line_after_nml.split("\n"))
        )

        nml.uppercase = True
        nml._writestream(output)
        output.write(line_after_nml)

        output.write(
            "    "
        )  # I have no idea why these spaces are necessary at the moment, something wrong with pandas...?
        data_block.to_string(
            output,
            index=False,
            formatters={"COLCODE": "{:12d}".format, "GLOBAL": "{:18.8e}".format},
        )

        output.write("\n")
        with open(filename, "w") as output_file:
            output.seek(0)
            copyfileobj(output, output_file)

    def _get_header(self):
        return self.minput.metadata["header"]

    def _get_nml_and_data_block(self):
        data_block = self._get_data_block()

        nml = Namelist()
        nml["THISFILE_SPECIFICATIONS"] = Namelist()
        nml["THISFILE_SPECIFICATIONS"]["THISFILE_DATACOLUMNS"] = (
            len(data_block.columns) - 1
        )
        nml["THISFILE_SPECIFICATIONS"]["THISFILE_FIRSTYEAR"] = data_block[
            "COLCODE"
        ].iloc[0]
        nml["THISFILE_SPECIFICATIONS"]["THISFILE_LASTYEAR"] = data_block[
            "COLCODE"
        ].iloc[-1]
        assert (
            (data_block["COLCODE"].iloc[-1] - data_block["COLCODE"].iloc[0] + 1)
            / len(data_block["COLCODE"])
            == 1.0
        )  # not ready for others yet
        nml["THISFILE_SPECIFICATIONS"]["THISFILE_ANNUALSTEPS"] = 1
        unique_units = self.minput.df.index.get_level_values("UNITS").unique()
        assert len(unique_units) == 1  # again not ready for other stuff
        nml["THISFILE_SPECIFICATIONS"]["THISFILE_UNITS"] = unique_units[0]
        regions = self.minput.df.index.get_level_values("REGION").unique()
        assert len(regions) == 1  # again not ready for other stuff
        assert regions[0] == "GLOBAL"  # again not ready for other stuff
        nml["THISFILE_SPECIFICATIONS"]["THISFILE_DATTYPE"] = "FOURBOXDATA"

        return nml, data_block

    def _get_data_block(self):
        raise NotImplementedError()


class HIST_CONC_INWriter(InputWriter):
    def _get_data_block(self):
        # lazy but works for now, will become smarter later
        data_block = self.minput.df[self.minput.df.index.values[0][:-1]]
        data_block = pd.DataFrame(
            data_block
        ).reset_index()  # the fact that I have to do this is problematic...
        assert len(data_block.columns == 2)  # only ready for global series now
        data_block.columns = ["COLCODE", "GLOBAL"]
        return data_block


def determine_tool(fname, regexp_map):
    for fname_regex in regexp_map:
        if re.match(fname_regex, basename(fname)):
            return regexp_map[fname_regex]


hist_emis_in_regexp = r"^HIST.*\_EMIS\.IN$"
hist_conc_in_regexp = r"^.*\_.*CONC.*\.IN$"

_fname_reader_regex_map = {
    hist_emis_in_regexp: HIST_EMIS_INReader,
    # r'^.*\.SCEN$': SCENReader,
    # r'^.*\.SCEN7$': SCEN7Reader,
    hist_conc_in_regexp: HIST_CONC_INReader,
    # r'^INVERSEEMIS\_.*\.OUT$': INVERSEEMIS_OUTReader,
    # r'.*\.SECTOR$': SECTORReader,
}


def get_reader(fname):
    return determine_tool(fname, _fname_reader_regex_map)(fname)


_fname_writer_regex_map = {
    # hist_emis_in_regexp: HIST_EMIS_INWriter,
    # r'^.*\.SCEN$': SCENWriter,
    # r'^.*\.SCEN7$': SCEN7Writer,
    hist_conc_in_regexp: HIST_CONC_INWriter,
    # r'^INVERSEEMIS\_.*\.OUT$': INVERSEEMIS_OUTWriter,
    # r'.*\.SECTOR$': SECTORWriter,
}


def get_writer(fname):
    return determine_tool(fname, _fname_writer_regex_map)()


class MAGICCInput(object):
    """
    An interface to read and write the input files used by MAGICC.

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

    TODO: Write example for writing

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

        # Parameters
        filename (str): Optional file name, including extension, for the target
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
            self._raise_not_loaded_error()
        if len(item) == 2:
            return self.df["value"][item[0], :, item[1], :, :]
        elif len(item) == 3:
            return self.df["value"][item[0], :, item[1], item[2], :]

    def __getattr__(self, item):
        """
        Proxy any attributes/functions on the dataframe
        """
        if not self.is_loaded:
            self._raise_not_loaded_error()
        return getattr(self.df, item)

    def _raise_not_loaded_error(self):
        raise ValueError("File has not been read from disk yet")

    @property
    def is_loaded(self):
        return self.df is not None

    def read(self, filepath=None, filename=None):
        """
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
            raise ValueError("Cannot find {}".format(filename))

        reader = get_reader(filename)
        self.metadata, self.df = reader.read()

    def write(self, filename):
        """
        TODO: Implement writing to disk
        """
        writer = get_writer(filename)
        writer.write(self, filename)
