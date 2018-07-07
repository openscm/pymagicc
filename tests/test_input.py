from os import remove
from os.path import dirname, join, isfile, basename
from tempfile import mkstemp, mkdtemp
from shutil import rmtree

import pandas as pd
import re
import pkg_resources
import pytest
from unittest.mock import patch
import f90nml

from pymagicc.api import MAGICC6
from pymagicc.input import MAGICCInput, MAGICC7Reader, MAGICC6Reader, InputReader, HIST_CONC_INReader

MAGICC6_DIR = pkg_resources.resource_filename('pymagicc', 'MAGICC6/run')
MAGICC7_DIR = join(dirname(__file__), "test_data")

# TEMPCHANGELOG:
# - stop reading in the nml. All the values in it should be introspected hence this step is redundant. If required as a check of file validity in future, we can write a separate function, it shouldn't be in the reader

# TODO:
# - write tests for SCEN and SCEN7 files

def test_load_magicc6_emis():
    mdata = MAGICCInput()
    assert mdata.is_loaded == False
    mdata.read(MAGICC6_DIR, 'HISTRCP_CO2I_EMIS.IN')
    assert mdata.is_loaded == True

    for key in ['units', 'firstdatarow', 'dattype']:
        with pytest.raises(KeyError):
            mdata.metadata[key]

    assert isinstance(mdata.metadata['header'], str)
    assert isinstance(mdata.df, pd.DataFrame)
    assert mdata.df.index.names == ['VARIABLE', 'TODO', 'REGION', 'YEAR', 'UNITS']
    assert mdata.df['value']['CO2I_EMIS', 'SET', 'R5ASIA', 2000, 'GtC'] == 1.76820270e+000


def test_load_magicc6_conc():
    mdata = MAGICCInput()
    mdata.read(MAGICC6_DIR, 'HISTRCP_CO2_CONC.IN')

    assert (mdata.df.index.get_level_values('UNITS') == 'ppm').all()
    assert mdata.df['CO2_CONC', 'SET', 'GLOBAL', 'ppm', 1048] == 2.80435733e+002


def test_load_magicc7_emis():
    mdata = MAGICCInput()
    mdata.read(MAGICC7_DIR, 'HISTSSP_CO2I_EMIS.IN')

    assert mdata.metadata['contact'] == 'Zebedee Nicholls, Australian-German Climate and Energy College, University of Melbourne, zebedee.nicholls@climate-energy-college.org'
    assert (mdata.df.index.get_level_values('UNITS') == 'GtC').all()
    assert mdata.df['CO2I', 'SET', 'R6REF', 'GtC', 2013] == 0.6638
    assert mdata.df['CO2I', 'SET', 'R6ASIA', 'GtC', 2000] == 1.6911

def test_load_prename():
    mdata = MAGICCInput('HISTSSP_CO2I_EMIS.IN')
    mdata.read(MAGICC7_DIR)

    assert (mdata.df.index.get_level_values('UNITS') == 'GtC').all()

    mdata.read(MAGICC6_DIR, 'HISTRCP_CO2_CONC.IN')
    assert (mdata.df.index.get_level_values('UNITS') == 'ppm').all()
    assert not (mdata.df.index.get_level_values('UNITS') == 'GtC').any()


def test_direct_access():
    mdata = MAGICCInput('HISTRCP_CO2I_EMIS.IN')
    mdata.read(MAGICC6_DIR)

    assert (mdata['CO2I_EMIS', 'R5LAM', 1983] == mdata.df['value']['CO2I_EMIS', :, 'R5LAM', 1983, :]).all()
    assert (mdata['CO2I_EMIS', 'R5LAM'] == mdata.df['value']['CO2I_EMIS', :, 'R5LAM', :, :]).all()


def test_lazy_load():
    mdata = MAGICCInput('HISTRCP_CO2I_EMIS.IN')
    # I don't know where the file is yet..
    with MAGICC6() as magicc:
        # and now load the data
        mdata.read(magicc.run_dir)
        assert mdata.df is not None


def test_proxy():
    mdata = MAGICCInput('HISTRCP_CO2I_EMIS.IN')
    mdata.read(MAGICC6_DIR)

    # Get an attribute from the pandas DataFrame
    plot = mdata.plot
    assert plot.__module__ == 'pandas.plotting._core'


def test_early_call():
    mdata = MAGICCInput('HISTRCP_CO2I_EMIS.IN')

    with pytest.raises(ValueError):
        mdata['CO2I']['R5LAM']

    with pytest.raises(ValueError):
        mdata.plot()

def test_no_name():
    mdata = MAGICCInput()
    with pytest.raises(AssertionError):
        mdata.read('/tmp')

def test_invalid_name():
    mdata = MAGICCInput()
    with pytest.raises(ValueError):
        mdata.read('/tmp', 'MYNONEXISTANT.IN')

def test_default_path():
    mdata = MAGICCInput('HISTRCP_CO2I_EMIS.IN')
    mdata.read()

def test_header_metadata():
    m6 = MAGICC6Reader('test')
    assert m6.process_header('lkhdsljdkjflkjndlkjlkndjgf') == {}
    assert m6.process_header('') == {}
    assert m6.process_header('Data: Average emissions per year') == {'data': 'Average emissions per year'}
    assert m6.process_header('DATA:  Historical landuse BC (BCB) Emissions (HISTRCP_BCB_EMIS) ') == {'data': 'Historical landuse BC (BCB) Emissions (HISTRCP_BCB_EMIS)'}
    assert m6.process_header('CONTACT:   RCP 3-PD (IMAGE): Detlef van Vuuren (detlef.vanvuuren@pbl.nl); RCP 4.5 (MiniCAM): Allison Thomson (Allison.Thomson@pnl.gov); RCP 6.0 (AIM): Toshihiko Masui (masui@nies.go.jp); RCP 8.5 (MESSAGE): Keywan Riahi (riahi@iiasa.ac.at); Base year emissions inventories: Steve Smith (ssmith@pnl.gov) and Jean-Francois Lamarque (Jean-Francois.Lamarque@noaa.gov) ') == {'contact': 'RCP 3-PD (IMAGE): Detlef van Vuuren (detlef.vanvuuren@pbl.nl); RCP 4.5 (MiniCAM): Allison Thomson (Allison.Thomson@pnl.gov); RCP 6.0 (AIM): Toshihiko Masui (masui@nies.go.jp); RCP 8.5 (MESSAGE): Keywan Riahi (riahi@iiasa.ac.at); Base year emissions inventories: Steve Smith (ssmith@pnl.gov) and Jean-Francois Lamarque (Jean-Francois.Lamarque@noaa.gov)'}
    # assert warning on this one
    # m6.process_header('DATE: 26/11/2009 11:29:06; MAGICC-VERSION: 6.3.09, 25 November 2009')

    m7 = MAGICC7Reader('test')
    assert m7.process_header('lkhdsljdkjflkjndlkjlkndjgf') == {}
    assert m7.process_header('') == {}
    assert m7.process_header('Data: Average emissions per year\nother text') == {'data': 'Average emissions per year'}
    assert m7.process_header('           Data: Average emissions per year    ') == {'data': 'Average emissions per year'}
    assert m7.process_header('Compiled by: Zebedee Nicholls, Australian-German Climate & Energy College') == {'compiled by': 'Zebedee Nicholls, Australian-German Climate & Energy College'}

@pytest.mark.parametrize('test_filename', [
    (None),
    ('test/filename.OUT')
])
def test_MAGICCInput_init(test_filename):
    if test_filename is None:
        mdata = MAGICCInput()
        assert mdata.name is None
    else:
        mdata = MAGICCInput(test_filename)
        assert mdata.name is test_filename

    assert mdata.df is None
    assert mdata.metadata == {}

def test_set_lines():
    reader = InputReader('test')
    with pytest.raises(FileNotFoundError):
        reader._set_lines()

    test_file = join(MAGICC7_DIR, 'HISTSSP_CO2I_EMIS.IN')
    assert isfile(test_file)

    reader = InputReader(test_file)
    reader._set_lines()
    with open(test_file) as f:
        assert reader.lines == f.readlines()

@pytest.mark.parametrize('test_filename, expected_variable', [
    ('/test/filename/paths/HISTABCD_CH4_CONC.IN', 'CH4_CONC'),
    ('test/filename.OUT', None),
])
def test_CONC_INReader_get_variable_from_filename(test_filename, expected_variable):

    conc_reader = HIST_CONC_INReader(test_filename)
    if expected_variable is None:
        expected_message = re.escape('Cannot determine variable from filename: {}'.format(test_filename))
        with pytest.raises(SyntaxError, match=expected_message):
            conc_reader._get_variable_from_filename()
    else:
        assert conc_reader._get_variable_from_filename() == expected_variable

@pytest.fixture
def temp_file():
    temp_file = mkstemp()[1]
    yield temp_file
    print('deleting {}'.format(temp_file))
    remove(temp_file)

@pytest.fixture
def temp_dir():
    temp_dir = mkdtemp()
    yield temp_dir
    print('deleting {}'.format(temp_dir))
    rmtree(temp_dir)

@pytest.mark.parametrize('starting_fpath, starting_fname', [
    (MAGICC6_DIR, 'HISTRCP_CO2_CONC.IN'),
])
def test_CONC_IN_file_read_write_functionally_identical(starting_fpath, starting_fname, temp_dir):
    mi_writer = MAGICCInput()
    mi_writer.read(filepath=starting_fpath, filename=starting_fname)

    mi_writer.write(join(temp_dir, starting_fname))

    mi_written = MAGICCInput()
    mi_written.read(filepath=temp_dir, filename=starting_fname)
    nml_written = f90nml.read(join(temp_dir, starting_fname))

    mi_initial = MAGICCInput()
    mi_initial.read(filepath=starting_fpath, filename=starting_fname)
    nml_initial = f90nml.read(join(temp_dir, starting_fname))

    assert mi_written.metadata == mi_initial.metadata
    assert (mi_written.df == mi_initial.df).all()
    assert sorted(nml_written['thisfile_specifications']) == sorted(nml_initial['thisfile_specifications'])
