import os

import pandas as pd


from pymagicc import (
    _magiccpath,
    _get_number_of_datapoints,
    _get_region_code,
    read_scen_file,
    write_scen_file,
    rcp3pd,
    rcp45,
    rcp6,
    rcp85,
    run
)


rcp3pd_scen_file = os.path.join(_magiccpath, "RCP3PD.SCEN")
rcp85_scen_file = os.path.join(_magiccpath, "RCP85.SCEN")
world_only = read_scen_file(os.path.join(os.path.dirname(__file__),
                            "./test_data/WORLD_ONLY.SCEN"))


def test_count():
    assert _get_number_of_datapoints(rcp3pd_scen_file) == 20


def test_region_code():
    assert _get_region_code(rcp3pd_scen_file) == 41


def test_read_scen_file():
    assert len(rcp3pd) == 7
    assert len(rcp3pd["WORLD"].index) == 20
    assert len(rcp3pd["WORLD"].columns) == 23


def test_read_world_only_scenario():
    world_only = read_scen_file(os.path.join(os.path.dirname(__file__),
                                "./test_data/WORLD_ONLY.SCEN"))
    assert isinstance(world_only, pd.DataFrame)
    assert len(world_only) == 5


def test_write_scen_file(tmpdir):
    outfile = tmpdir.join("SCENARIO.SCEN")
    write_scen_file(rcp3pd, outfile)
    output = read_scen_file(os.path.join(outfile.dirname, outfile.basename))
    assert len(rcp3pd) == len(output)
    assert len(rcp3pd["WORLD"].index) == len(output["WORLD"].index)
    assert len(rcp3pd["WORLD"].columns) == len(output["WORLD"].columns)
    assert rcp3pd["WORLD"].equals(output["WORLD"])


def test_write_scen_file_world_only(tmpdir):
    outfile = tmpdir.join("SCENARIO.SCEN")
    write_scen_file(world_only, outfile)
    output = read_scen_file(os.path.join(outfile.dirname, outfile.basename))
    assert len(world_only) == len(output)
    assert len(world_only.index) == len(output.index)
    assert len(world_only.columns) == len(output.columns)
    assert world_only.equals(output)


def test_run_rcp3pd():
    results = run(rcp3pd)
    surface_temp = pd.read_csv(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "original_data/RCP3PD/DAT_SURFACE_TEMP.OUT"),
        delim_whitespace=True,
        skiprows=19,
        index_col=0
    )

    assert surface_temp.GLOBAL.equals(results["SURFACE_TEMP"].GLOBAL)


def test_run_rcp45():
    results = run(rcp45)
    surface_temp = pd.read_csv(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "original_data/RCP45/DAT_SURFACE_TEMP.OUT"),
        delim_whitespace=True,
        skiprows=19,
        index_col=0
    )

    assert surface_temp.GLOBAL.equals(results["SURFACE_TEMP"].GLOBAL)


def test_run_rcp6():
    results = run(rcp6)
    surface_temp = pd.read_csv(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "original_data/RCP6/DAT_SURFACE_TEMP.OUT"),
        delim_whitespace=True,
        skiprows=19,
        index_col=0
    )

    assert surface_temp.GLOBAL.equals(results["SURFACE_TEMP"].GLOBAL)


def test_run_rcp85():
    results = run(rcp85)
    surface_temp = pd.read_csv(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "./original_data/RCP85/DAT_SURFACE_TEMP.OUT"),
        delim_whitespace=True,
        skiprows=19,
        index_col=0
    )

    assert surface_temp.GLOBAL.equals(results["SURFACE_TEMP"].GLOBAL)


def test_parameters():
    _, params = run(rcp3pd, return_config=True, core_climatesensitivity=1.5)
    assert params["core_climatesensitivity"] == 1.5
    # Test removal of newlines in PARAMETERS.out
    assert 'H\nFC134a' not in params["fgas_names"]
