from os.path import dirname, join

import pandas as pd
import pkg_resources
import pytest

from pymagicc.api import MAGICC6
from pymagicc.input import MAGICCInput, MAGICC7Reader, MAGICC6Reader

MAGICC6_DIR = pkg_resources.resource_filename('pymagicc', 'MAGICC6/run')
MAGICC7_DIR = join(dirname(__file__), "test_data")


def test_load_magicc6_emis():
    mdata = MAGICCInput()
    assert mdata.is_loaded == False
    mdata.read(MAGICC6_DIR, 'HISTRCP_CO2I_EMIS.IN')
    assert mdata.is_loaded == True

    assert mdata.metadata['units']['CO2I'] == 'GtC'
    assert mdata.metadata['dattype'] == 'REGIONDATA'
    assert isinstance(mdata.metadata['header'], str)
    assert isinstance(mdata.df, pd.DataFrame)
    assert mdata.df['CO2I']['R5ASIA'][2000] == 1.76820270e+000


def test_load_magicc6_conc():
    mdata = MAGICCInput()
    mdata.read(MAGICC6_DIR, 'HISTRCP_CO2_CONC.IN')

    assert mdata.metadata['units']['CO2'] == 'ppm'


def test_load_magicc7_emis():
    mdata = MAGICCInput()
    mdata.read(MAGICC7_DIR, 'HISTSSP_CO2I_EMIS.IN')

    assert mdata.metadata['units']['CO2I'] == 'GtC'
    assert mdata.metadata['contact'] == 'Zebedee Nicholls, Australian-German Climate and Energy College, University of Melbourne, zebedee.nicholls@climate-energy-college.org'
    assert mdata.df['CO2I']['R6ASIA'][2000] == 1.6911



def test_load_prename():
    mdata = MAGICCInput('HISTSSP_CO2I_EMIS.IN')
    mdata.read(MAGICC7_DIR)

    assert mdata.metadata['units']['CO2I'] == 'GtC'

    mdata.read(MAGICC6_DIR, 'HISTRCP_CO2_CONC.IN')
    assert mdata.metadata['units']['CO2'] == 'ppm'
    assert 'CO2I' not in mdata.metadata['units']


def test_direct_access():
    mdata = MAGICCInput('HISTRCP_CO2I_EMIS.IN')
    mdata.read(MAGICC6_DIR)

    assert (mdata['CO2I']['R5LAM'] == mdata.df['CO2I']['R5LAM']).all()


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
    m6 = MAGICC6Reader('test', [])
    assert m6.process_header('lkhdsljdkjflkjndlkjlkndjgf') == {}
    assert m6.process_header('') == {}
    assert m6.process_header('Data: Average emissions per year') == {'data': 'Average emissions per year'}
    assert m6.process_header('DATA:  Historical landuse BC (BCB) Emissions (HISTRCP_BCB_EMIS) ') == {'data': 'Historical landuse BC (BCB) Emissions (HISTRCP_BCB_EMIS)'}
    assert m6.process_header('CONTACT:   RCP 3-PD (IMAGE): Detlef van Vuuren (detlef.vanvuuren@pbl.nl); RCP 4.5 (MiniCAM): Allison Thomson (Allison.Thomson@pnl.gov); RCP 6.0 (AIM): Toshihiko Masui (masui@nies.go.jp); RCP 8.5 (MESSAGE): Keywan Riahi (riahi@iiasa.ac.at); Base year emissions inventories: Steve Smith (ssmith@pnl.gov) and Jean-Francois Lamarque (Jean-Francois.Lamarque@noaa.gov) ') == {'contact': 'RCP 3-PD (IMAGE): Detlef van Vuuren (detlef.vanvuuren@pbl.nl); RCP 4.5 (MiniCAM): Allison Thomson (Allison.Thomson@pnl.gov); RCP 6.0 (AIM): Toshihiko Masui (masui@nies.go.jp); RCP 8.5 (MESSAGE): Keywan Riahi (riahi@iiasa.ac.at); Base year emissions inventories: Steve Smith (ssmith@pnl.gov) and Jean-Francois Lamarque (Jean-Francois.Lamarque@noaa.gov)'}
    # assert warning on this one
    # m6.process_header('DATE: 26/11/2009 11:29:06; MAGICC-VERSION: 6.3.09, 25 November 2009')

    m7 = MAGICC7Reader('test', [])
    assert m7.process_header('lkhdsljdkjflkjndlkjlkndjgf') == {}
    assert m7.process_header('') == {}
    assert m7.process_header('Data: Average emissions per year\nother text') == {'data': 'Average emissions per year'}
    assert m7.process_header('           Data: Average emissions per year    ') == {'data': 'Average emissions per year'}
    assert m7.process_header('Compiled by: Zebedee Nicholls, Australian-German Climate & Energy College') == {'compiled by': 'Zebedee Nicholls, Australian-German Climate & Energy College'}
