import os

import pandas as pd
import pytest
from pymagicc import (
    _magiccpath,
    _get_number_of_datapoints,
    _get_region_code,
    read_scen_file,
    write_scen_file,
    rcp26,
    rcp45,
    rcp60,
    rcp85,
    run,
)

rcp26_scen_file = os.path.join(_magiccpath, "RCP26.SCEN")
rcp85_scen_file = os.path.join(_magiccpath, "RCP85.SCEN")
world_only = read_scen_file(
    os.path.join(os.path.dirname(__file__), "./test_data/WORLD_ONLY.SCEN")
)


def test_count():
    assert _get_number_of_datapoints(rcp26_scen_file) == 20


def test_region_code():
    assert _get_region_code(rcp26_scen_file) == 41


def test_read_scen_file():
    assert len(rcp26) == 7
    assert len(rcp26["WORLD"].index) == 20
    assert len(rcp26["WORLD"].columns) == 23


def test_read_world_only_scenario():
    world_only = read_scen_file(
        os.path.join(os.path.dirname(__file__), "./test_data/WORLD_ONLY.SCEN")
    )
    assert isinstance(world_only, pd.DataFrame)
    assert len(world_only) == 5


def test_write_scen_file(tmpdir):
    outfile = tmpdir.join("SCENARIO.SCEN")
    write_scen_file(rcp26, outfile)
    outfile_path = os.path.join(outfile.dirname, outfile.basename)
    output = read_scen_file(outfile_path)
    assert len(rcp26) == len(output)
    assert len(rcp26["WORLD"].index) == len(output["WORLD"].index)
    assert len(rcp26["WORLD"].columns) == len(output["WORLD"].columns)
    assert rcp26["WORLD"].equals(output["WORLD"])


def test_write_scen_file_world_only(tmpdir):
    outfile = tmpdir.join("SCENARIO.SCEN")
    write_scen_file(world_only, outfile)
    output = read_scen_file(os.path.join(outfile.dirname, outfile.basename))
    assert len(world_only) == len(output)
    assert len(world_only.index) == len(output.index)
    assert len(world_only.columns) == len(output.columns)
    assert world_only.equals(output)


@pytest.mark.slow
def test_run_rcp26():
    results = run(rcp26)
    surface_temp = pd.read_csv(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "original_data/RCP26/DAT_SURFACE_TEMP.OUT",
        ),
        delim_whitespace=True,
        skiprows=19,
        index_col=0,
    )

    assert surface_temp.GLOBAL.equals(results["SURFACE_TEMP"].GLOBAL)


@pytest.mark.slow
def test_run_rcp45():
    results = run(rcp45)
    surface_temp = pd.read_csv(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "original_data/RCP45/DAT_SURFACE_TEMP.OUT",
        ),
        delim_whitespace=True,
        skiprows=19,
        index_col=0,
    )

    assert surface_temp.GLOBAL.equals(results["SURFACE_TEMP"].GLOBAL)


@pytest.mark.slow
def test_run_rcp60():
    results = run(rcp60)
    surface_temp = pd.read_csv(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "original_data/RCP60/DAT_SURFACE_TEMP.OUT",
        ),
        delim_whitespace=True,
        skiprows=19,
        index_col=0,
    )

    assert surface_temp.GLOBAL.equals(results["SURFACE_TEMP"].GLOBAL)


@pytest.mark.slow
def test_run_rcp85():
    results = run(rcp85)
    surface_temp = pd.read_csv(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "./original_data/RCP85/DAT_SURFACE_TEMP.OUT",
        ),
        delim_whitespace=True,
        skiprows=19,
        index_col=0,
    )

    assert surface_temp.GLOBAL.equals(results["SURFACE_TEMP"].GLOBAL)


@pytest.mark.slow
def test_parameters():
    _, params = run(rcp26, return_config=True, core_climatesensitivity=1.5)
    assert params["allcfgs"]["core_climatesensitivity"] == 1.5
    # Test removal of newlines in PARAMETERS.out
    assert "H\nFC134a" not in params["allcfgs"]["fgas_names"]


@pytest.mark.slow
def test_default_config():
    _, conf = run(rcp26, return_config=True)
    assert conf["allcfgs"]["core_climatesensitivity"] == 3
    assert conf["years"]["startyear"] == 1765


@pytest.mark.slow
def test_set_years():
    results, conf = run(rcp26, return_config=True, startyear=1900, endyear=2000)
    assert conf["years"]["startyear"] == 1900
    assert conf["years"]["endyear"] == 2000
    assert results["SURFACE_TEMP"].GLOBAL.index[0] == 1900
    assert results["SURFACE_TEMP"].GLOBAL.index[-1] == 2000
