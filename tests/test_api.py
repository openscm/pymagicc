from os import remove
from os.path import exists, join
from subprocess import CalledProcessError

import f90nml
import pytest

from pymagicc.api import MAGICC6, MAGICC7, config


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
    config['EXECUTABLE'] = '/tmp/magicc'
    magicc = MAGICC6()

    # Stop this override impacting other tests
    del config.overrides['EXECUTABLE']
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
