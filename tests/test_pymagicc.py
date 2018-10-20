import os


import pandas as pd
import pytest


from pymagicc import _magiccpath, read_scen_file, rcp26, rcp45, rcp60, rcp85, run


RCP26_SCEN_FILE = os.path.join(_magiccpath, "RCP26.SCEN")
RCP85_SCEN_FILE = os.path.join(_magiccpath, "RCP85.SCEN")
WORLD_ONLY = read_scen_file(
    os.path.join(os.path.dirname(__file__), "./test_data/WORLD_ONLY.SCEN")
)


def test_read_scen_file():
    assert False


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


@pytest.mark.slow
def test_out_carboncycle():
    out = run(rcp26, out_carboncycle=1)
    assert "CARBONCYCLE" in out.keys()
