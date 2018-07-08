from os import remove
from os.path import exists, join
from subprocess import CalledProcessError

import numpy as np
import pytest
from unittest.mock import patch
import pandas as pd
import f90nml

from pymagicc.api import MAGICC6, MAGICC7, config, _clean_value


@pytest.fixture(scope="module", params=[MAGICC6, MAGICC7])
def package(request):
    MAGICC_cls = request.param
    p = MAGICC_cls()

    if p.executable is None or not exists(p.original_dir):
        pytest.skip('MAGICC {} is not available'.format(p.version))
    p.create_copy()
    root_dir = p.root_dir
    yield p
    # Perform cleanup after tests are complete
    p.remove_temp_copy()
    assert not exists(root_dir)


def write_config(p):
    emis_key = "file_emissionscenario" if p.version == 6 \
        else "FILE_EMISSCEN"
    outpath = join(p.run_dir, "MAGTUNE_SIMPLE.CFG")
    f90nml.write({"nml_allcfgs": {
        emis_key: 'RCP26.SCEN'
    }}, outpath, force=True)

    # Write years config.
    outpath_years = join(p.run_dir, "MAGCFG_NMLYEARS.CFG")
    f90nml.write({"nml_years": {
        "startyear": 1765,
        "endyear": 2100,
        "stepsperyear": 12
    }}, outpath_years, force=True)


def test_not_initalise():
    p = MAGICC6()
    assert p.root_dir is None
    assert p.run_dir is None
    assert p.out_dir is None


def test_initalise_and_clean(package):
    # fixture package has already been initialised
    assert exists(package.run_dir)
    assert exists(join(package.run_dir, 'MAGCFG_USER.CFG'))
    assert exists(package.out_dir)


def test_run_failure(package):
    # Ensure that no MAGCFG_NMLYears.cfg is present
    if exists(join(package.run_dir, 'MAGCFG_NMLYEARS.CFG')):
        remove(join(package.run_dir, 'MAGCFG_NMLYEARS.CFG'))

    with pytest.raises(CalledProcessError):
        package.run()

    assert len(package.config.keys()) == 0


def test_run_success(package):
    write_config(package)
    results = package.run()

    assert len(results.keys()) > 1
    assert 'SURFACE_TEMP' in results

    assert len(package.config.keys()) != 0


def test_run_only(package):
    write_config(package)
    results = package.run(only=['SURFACE_TEMP'])

    assert len(results.keys()) == 1
    assert 'SURFACE_TEMP' in results


def test_override_config():
    config['EXECUTABLE_6'] = '/tmp/magicc'
    magicc = MAGICC6()

    # Stop this override impacting other tests
    del config.overrides['EXECUTABLE_6']
    assert magicc.executable == '/tmp/magicc'


def test_dont_create_dir():
    magicc = MAGICC6()
    # Dir isn't created yet
    assert magicc.root_dir is None
    magicc.create_copy()
    root_dir = magicc.root_dir
    assert exists(root_dir)
    magicc.remove_temp_copy()
    assert not exists(root_dir)
    assert magicc.root_dir is None


def test_clean_value_simple():
    assert "SF6" == _clean_value("SF6                 ")

    assert 1970 == _clean_value(1970)
    assert 2012.123 == _clean_value(2012.123)


def test_clean_value_nulls():
    in_str = [
        "SF6                 ", "SO2F2               ",
        "\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000",
        "\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000",
    ]
    expected = ["SF6", "SO2F2", "", ""]
    out_str = _clean_value(in_str)

    assert len(out_str) == len(expected)
    for o, e in zip(out_str, expected):
        assert o == e


def test_incorrect_subdir():
    config['EXECUTABLE_6'] = '/tmp/magicc'
    magicc = MAGICC6()
    try:
        with pytest.raises(AssertionError):
            magicc.create_copy()
    finally:
        del config.overrides['EXECUTABLE_6']
        magicc.remove_temp_copy()


def test_root_dir():
    with MAGICC6() as magicc:
        m2 = MAGICC6(root_dir=magicc.root_dir)

        assert m2.root_dir == magicc.root_dir

        # Does nothing
        m2.remove_temp_copy()
        # Can be called many times
        m2.remove_temp_copy()

        assert m2.root_dir is not None

def test_no_root_dir():
    assert not exists('/tmp/magicc/')
    magicc = MAGICC6(root_dir='/tmp/magicc/')

    with pytest.raises(FileNotFoundError):
        magicc.run()

def test_diagnose_tcr_ecs(package):
    mock_tcr_val = 1.8
    mock_tcr_yr = 1825
    mock_ecs_val = 3.1
    mock_ecs_yr = 2200

    mock_res = {}
    fake_time = np.arange(1750, 2200)
    mock_res['SURFACE_TEMP'] = pd.DataFrame(
        {'GLOBAL': np.zeros(len(fake_time))},
        index=fake_time,
    )

    mock_res['SURFACE_TEMP']['GLOBAL'].loc[mock_tcr_yr] = mock_tcr_val
    mock_res['SURFACE_TEMP']['GLOBAL'].loc[mock_ecs_yr] = mock_ecs_val

    with patch.object(package, '_diagnose_tcr_ecs_config_setup') as mock_diagnose_tcr_ecs_setup:
        mock_diagnose_tcr_ecs_setup.return_value = [mock_tcr_yr, mock_ecs_yr]

        with patch.object(package, 'run') as mock_run:
            mock_run.return_value = mock_res
            assert package.diagnose_tcr_ecs()['tcr'] == mock_tcr_val
            assert mock_diagnose_tcr_ecs_setup.call_count == 1
            mock_run.assert_called_with(only=['SURFACE_TEMP'])
            assert package.diagnose_tcr_ecs()['ecs'] == mock_ecs_val
            assert mock_diagnose_tcr_ecs_setup.call_count == 2

def test_diagnose_tcr_ecs_config_setup(package):
    with patch.object(package, 'set_years') as mock_set_years:

# at one level have to check that CO2 concs come out as expected (and error if not) and that total forcing is linear (and error if not) and that temperature is monotonic increasing (and error if not)
# test that 1PCT CO2 file hasn't changed (and error if it has)

# integration test (i.e. actually runs magicc) hence slow
@pytest.mark.slow
def test_integration_diagnose_tcr_ecs(package):
    actual_result = package.diagnose_tcr_ecs()
    assert isinstance(actual_result, dict)
    assert 'tcr' in actual_result
    assert 'ecs' in actual_result
    assert actual_result['tcr'] < actual_result['ecs']
    if isinstance(package, MAGICC6):
        assert actual_result['tcr'] == 1.970709 # MAGICC6 shipped with pymagicc should be stable
        assert actual_result['ecs'] == 2.982 # MAGICC6 shipped with pymagicc should be stable
