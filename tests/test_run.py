from os import remove
from os.path import exists, join
from subprocess import CalledProcessError

import f90nml
import pytest
from mock import patch
from pymagicc.compat import get_param
from pymagicc.run import MAGICC


@pytest.fixture(scope="module")
def package():
    p = MAGICC()
    p.create_copy()
    yield p
    # Perform cleanup after tests are complete
    p.remove_temp_copy()
    assert not exists(p.root_dir)


def write_config(p):
    outpath = join(p.run_dir, "MAGTUNE_SIMPLE.CFG")
    f90nml.write({"nml_allcfgs": {
        get_param('emission_scenario_key'): 'RCP26.SCEN'
    }}, outpath, force=True)

    # Write years config.
    outpath_years = join(p.run_dir, "MAGCFG_NMLYEARS.CFG")
    f90nml.write({"nml_years": {
        "startyear": 1765,
        "endyear": 2100,
        "stepsperyear": 12
    }}, outpath_years, force=True)


def test_not_initalise():
    p = MAGICC()
    assert exists(p.root_dir)
    assert not exists(p.run_dir)


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


def test_with():
    with MAGICC() as p:
        write_config(p)
        p.run()

        # keep track of run dir
        run_dir = p.run_dir

    # Check that run dir was automatically cleaned up
    assert not exists(run_dir)


@patch.object(MAGICC, 'is_initialised')
def test_with_init_once(mock_is_initialised):
    with patch.object(MAGICC, 'create_copy') as mock_init:
        # Check that init not called if is_initialised is true
        mock_is_initialised.return_value = True
        with MAGICC():
            pass
        mock_init.assert_not_called()

        mock_is_initialised.return_value = False
        with MAGICC():
            pass
        mock_init.assert_called_once()


def test_is_initalised():
    p = MAGICC()
    assert not p.is_initialised()
    p.create_copy()
    assert p.is_initialised()

    # test a duplicated object
    p2 = MAGICC(p.root_dir)
    assert p2.is_initialised()
