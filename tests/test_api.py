from os import remove, environ
from os.path import exists, join
from subprocess import CalledProcessError

import numpy as np
import pytest
from unittest.mock import patch
import pandas as pd
import f90nml

from pymagicc.api import MAGICCBase, MAGICC6, MAGICC7, config, _clean_value
from pymagicc.io import MAGICCData
from .test_config import config_override  #  noqa


@pytest.fixture(scope="function")
def magicc_base():
    yield MAGICCBase()


@pytest.fixture(scope="function", params=[MAGICC6, MAGICC7])
def package(request):
    MAGICC_cls = request.param
    p = MAGICC_cls()

    if p.executable is None or not exists(p.original_dir):
        magicc_x_unavailable = "MAGICC {} is not available.".format(p.version)
        env_text = "Pymagicc related variables in your current environment are: {}.".format(";".join(["{}: {}".format(k, v) for (k,v) in environ.items() if k.startswith("MAGICC_")]))
        env_help = "If you set MAGICC_EXECUTABLE_X=/path/to/MAGICCX/binary then you will be able to run the tests with that binary for MAGICC_X."
        pytest.skip("\n".join([magicc_x_unavailable, env_text, env_help]))
    p.create_copy()
    root_dir = p.root_dir
    yield p
    # Perform cleanup after tests are complete
    p.remove_temp_copy()
    assert not exists(root_dir)


def write_config(p):
    emis_key = "file_emissionscenario" if p.version == 6 else "FILE_EMISSCEN"
    outpath = join(p.run_dir, "MAGTUNE_SIMPLE.CFG")
    f90nml.write({"nml_allcfgs": {emis_key: "RCP26.SCEN"}}, outpath, force=True)

    # Write years config.
    outpath_years = join(p.run_dir, "MAGCFG_NMLYEARS.CFG")
    f90nml.write(
        {"nml_years": {"startyear": 1765, "endyear": 2100, "stepsperyear": 12}},
        outpath_years,
        force=True,
    )


def test_not_initalise():
    p = MAGICC6()
    assert p.root_dir is None
    assert p.run_dir is None
    assert p.out_dir is None


def test_initalise_and_clean(package):
    # fixture package has already been initialised
    assert exists(package.run_dir)
    assert exists(join(package.run_dir, "MAGCFG_USER.CFG"))
    assert exists(package.out_dir)


def test_run_failure(package):
    # Ensure that no MAGCFG_NMLYears.cfg is present
    if exists(join(package.run_dir, "MAGCFG_NMLYEARS.CFG")):
        remove(join(package.run_dir, "MAGCFG_NMLYEARS.CFG"))

    with pytest.raises(CalledProcessError):
        package.run()

    assert package.config is None


def test_run_success(package):
    write_config(package)
    results = package.run()

    assert len(results.keys()) > 1
    assert "SURFACE_TEMP" in results

    assert len(package.config.keys()) != 0


def test_run_only(package):
    write_config(package)
    results = package.run(only=["SURFACE_TEMP"])

    assert len(results.keys()) == 1
    assert "SURFACE_TEMP" in results


def test_override_config():
    config["EXECUTABLE_6"] = "/tmp/magicc"
    magicc = MAGICC6()

    # Stop this override impacting other tests
    del config.overrides["EXECUTABLE_6"]
    assert magicc.executable == "/tmp/magicc"


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
        "SF6                 ",
        "SO2F2               ",
        "\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000",
        "\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000",
    ]
    expected = ["SF6", "SO2F2", "", ""]
    out_str = _clean_value(in_str)

    assert len(out_str) == len(expected)
    for o, e in zip(out_str, expected):
        assert o == e


def test_incorrect_subdir():
    config["EXECUTABLE_6"] = "/tmp/magicc"
    magicc = MAGICC6()
    try:
        with pytest.raises(FileNotFoundError):
            magicc.create_copy()
    finally:
        del config.overrides["EXECUTABLE_6"]
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
    assert not exists("/tmp/magicc/")
    magicc = MAGICC6(root_dir="/tmp/magicc/")

    with pytest.raises(FileNotFoundError):
        magicc.run()


@patch.object(MAGICCBase, "_diagnose_tcr_ecs_config_setup")
@patch.object(MAGICCBase, "run")
@patch.object(MAGICCBase, "_get_tcr_ecs_from_diagnosis_results")
def test_diagnose_tcr_ecs(
    mock_get_tcr_ecs_from_results, mock_run, mock_diagnose_tcr_ecs_setup, magicc_base
):
    mock_tcr_val = 1.8
    mock_ecs_val = 3.1
    mock_results = pd.DataFrame()

    mock_run.return_value = mock_results
    mock_get_tcr_ecs_from_results.return_value = [mock_tcr_val, mock_ecs_val]

    assert magicc_base.diagnose_tcr_ecs()["tcr"] == mock_tcr_val
    assert mock_diagnose_tcr_ecs_setup.call_count == 1
    mock_run.assert_called_with(
        only=["CO2_CONC", "TOTAL_INCLVOLCANIC_RF", "SURFACE_TEMP"]
    )
    assert mock_get_tcr_ecs_from_results.call_count == 1
    mock_get_tcr_ecs_from_results.assert_called_with(mock_run())

    assert magicc_base.diagnose_tcr_ecs()["ecs"] == mock_ecs_val
    assert mock_diagnose_tcr_ecs_setup.call_count == 2
    assert mock_get_tcr_ecs_from_results.call_count == 2

    results = magicc_base.diagnose_tcr_ecs()
    assert isinstance(results["timeseries"], pd.DataFrame)


@patch.object(MAGICCBase, "update_config")
@patch.object(MAGICCBase, "set_years")
def test_diagnose_tcr_ecs_config_setup(mock_set_years, mock_update_config, magicc_base):
    magicc_base._diagnose_tcr_ecs_config_setup()
    mock_set_years.assert_called_with(startyear=1750, endyear=4200)
    mock_update_config.assert_called_with(
        FILE_CO2_CONC="TCRECS_CO2_CONC.IN",
        RF_TOTAL_CONSTANTAFTERYR=2000,
        RF_TOTAL_RUNMODUS="CO2",
    )


@pytest.fixture
def valid_tcr_ecs_diagnosis_results():
    startyear = 1700
    endyear = 4000
    spin_up_time = 50
    rising_time = 70
    tcr_yr = startyear + spin_up_time + rising_time
    ecs_yr = endyear
    fake_PI_conc = 278.0
    eqm_time = endyear - startyear - spin_up_time - rising_time

    fake_time = np.arange(startyear, endyear + 1)
    fake_concs = np.concatenate(
        (
            fake_PI_conc * np.ones(spin_up_time),
            fake_PI_conc * 1.01 ** (np.arange(rising_time + 1)),
            fake_PI_conc * 1.01 ** (rising_time) * np.ones(eqm_time),
        )
    )
    fake_rf = 2.0 * np.log(fake_concs / fake_PI_conc)
    fake_temp = np.log(fake_rf + 1.0) + fake_time / fake_time[1400]

    mock_results = {}
    mock_results["CO2_CONC"] = pd.DataFrame({"GLOBAL": fake_concs}, index=fake_time)
    mock_results["TOTAL_INCLVOLCANIC_RF"] = pd.DataFrame(
        {"GLOBAL": fake_rf}, index=fake_time
    )
    mock_results["SURFACE_TEMP"] = pd.DataFrame({"GLOBAL": fake_temp}, index=fake_time)
    yield {"mock_results": mock_results, "tcr_yr": tcr_yr, "ecs_yr": ecs_yr}


@patch.object(MAGICCBase, "_check_tcr_ecs_temp")
@patch.object(MAGICCBase, "_check_tcr_ecs_total_RF")
@patch.object(MAGICCBase, "_get_tcr_ecs_yr_from_CO2_concs")
def test_get_tcr_ecs_from_diagnosis_results(
    mock_get_tcr_ecs_yr_from_CO2_concs,
    mock_check_tcr_ecs_total_RF,
    mock_check_tcr_ecs_temp,
    valid_tcr_ecs_diagnosis_results,
    magicc_base,
):
    test_tcr_yr = valid_tcr_ecs_diagnosis_results["tcr_yr"]
    test_ecs_yr = valid_tcr_ecs_diagnosis_results["ecs_yr"]
    test_results_dict = valid_tcr_ecs_diagnosis_results["mock_results"]

    mock_get_tcr_ecs_yr_from_CO2_concs.return_value = [test_tcr_yr, test_ecs_yr]

    expected_tcr = test_results_dict["SURFACE_TEMP"]["GLOBAL"].loc[test_tcr_yr]
    expected_ecs = test_results_dict["SURFACE_TEMP"]["GLOBAL"].loc[test_ecs_yr]

    actual_tcr, actual_ecs = magicc_base._get_tcr_ecs_from_diagnosis_results(
        test_results_dict
    )
    assert actual_tcr == expected_tcr
    assert actual_ecs == expected_ecs

    mock_get_tcr_ecs_yr_from_CO2_concs.assert_called_with(
        test_results_dict["CO2_CONC"]["GLOBAL"]
    )
    mock_check_tcr_ecs_total_RF.assert_called_with(
        test_results_dict["TOTAL_INCLVOLCANIC_RF"]["GLOBAL"],
        tcr_yr=test_tcr_yr,
        ecs_yr=test_ecs_yr,
    )
    mock_check_tcr_ecs_temp.assert_called_with(
        test_results_dict["SURFACE_TEMP"]["GLOBAL"]
    )


def test_get_tcr_ecs_yr_from_CO2_concs(valid_tcr_ecs_diagnosis_results, magicc_base):
    test_CO2_data = valid_tcr_ecs_diagnosis_results["mock_results"]["CO2_CONC"][
        "GLOBAL"
    ]
    actual_tcr_yr, actual_ecs_yr = magicc_base._get_tcr_ecs_yr_from_CO2_concs(
        test_CO2_data
    )
    assert actual_tcr_yr == valid_tcr_ecs_diagnosis_results["tcr_yr"]
    assert actual_ecs_yr == valid_tcr_ecs_diagnosis_results["ecs_yr"]

    test_time = test_CO2_data.index.values
    for year_to_break in [
        test_time[0],
        test_time[15],
        test_time[115],
        test_time[-1] - 100,
        test_time[-1],
    ]:
        broken_CO2_data = test_CO2_data.copy()
        broken_CO2_data.loc[year_to_break] = test_CO2_data.loc[year_to_break] * 1.01
        with pytest.raises(ValueError, match=r"The TCR/ECS CO2 concs look wrong.*"):
            magicc_base._get_tcr_ecs_yr_from_CO2_concs(broken_CO2_data)


def test_check_tcr_ecs_total_RF(valid_tcr_ecs_diagnosis_results, magicc_base):
    test_RF_data = valid_tcr_ecs_diagnosis_results["mock_results"][
        "TOTAL_INCLVOLCANIC_RF"
    ]["GLOBAL"]
    magicc_base._check_tcr_ecs_total_RF(
        test_RF_data,
        valid_tcr_ecs_diagnosis_results["tcr_yr"],
        valid_tcr_ecs_diagnosis_results["ecs_yr"],
    )
    test_time = test_RF_data.index.values
    for year_to_break in [
        test_time[0],
        test_time[15],
        test_time[115],
        test_time[-1] - 100,
        test_time[-1],
    ]:
        broken_CO2_data = test_RF_data.copy()
        broken_CO2_data.loc[year_to_break] = (
            test_RF_data.loc[year_to_break] * 1.01 + 0.01
        )
        with pytest.raises(
            ValueError, match=r"The TCR/ECS total radiative forcing looks wrong.*"
        ):
            magicc_base._check_tcr_ecs_total_RF(
                broken_CO2_data,
                valid_tcr_ecs_diagnosis_results["tcr_yr"],
                valid_tcr_ecs_diagnosis_results["ecs_yr"],
            )


def test_check_tcr_ecs_temp(valid_tcr_ecs_diagnosis_results, magicc_base):
    test_temp_data = valid_tcr_ecs_diagnosis_results["mock_results"]["SURFACE_TEMP"][
        "GLOBAL"
    ]
    magicc_base._check_tcr_ecs_temp(test_temp_data)

    test_time = test_temp_data.index.values
    for year_to_break in [
        test_time[3],
        test_time[15],
        test_time[115],
        test_time[-1] - 100,
        test_time[-1],
    ]:
        broken_temp_data = test_temp_data.copy()
        broken_temp_data.loc[year_to_break] = (
            test_temp_data.loc[year_to_break - 1] - 0.1
        )
        with pytest.raises(
            ValueError,
            match=r"The TCR/ECS surface temperature looks wrong, it decreases",
        ):
            magicc_base._check_tcr_ecs_temp(broken_temp_data)


# integration test (i.e. actually runs magicc) hence slow
@pytest.mark.slow
def test_integration_diagnose_tcr_ecs(package):
    actual_result = package.diagnose_tcr_ecs()
    assert isinstance(actual_result, dict)
    assert "tcr" in actual_result
    assert "ecs" in actual_result
    assert actual_result["tcr"] < actual_result["ecs"]
    if isinstance(package, MAGICC6):
        assert (
            actual_result["tcr"] == 1.9733976000000002
        )  # MAGICC6 shipped with pymagicc should be stable
        assert (
            actual_result["ecs"] == 2.9968448
        )  # MAGICC6 shipped with pymagicc should be stable


def test_missing_config(config_override):
    with MAGICC6():
        pass
    config_override("EXECUTABLE_6", "")
    with pytest.raises(FileNotFoundError):
        with MAGICC6():
            pass

    config_override("EXECUTABLE_6", "/invalid/path")
    with pytest.raises(FileNotFoundError):
        with MAGICC6():
            pass

    config_override("EXECUTABLE_7", "")
    with pytest.raises(FileNotFoundError):
        with MAGICC7():
            pass


@patch.object(MAGICCBase, "_diagnose_tcr_ecs_config_setup")
@patch.object(MAGICCBase, "run")
@patch.object(MAGICCBase, "_get_tcr_ecs_from_diagnosis_results")
def test_diagnose_tcr_ecs(
    mock_get_tcr_ecs_from_results, mock_run, mock_diagnose_tcr_ecs_setup, magicc_base
):
    mock_tcr_val = 1.8
    mock_ecs_val = 3.1
    mock_results = pd.DataFrame()

    mock_run.return_value = mock_results
    mock_get_tcr_ecs_from_results.return_value = [mock_tcr_val, mock_ecs_val]

    assert magicc_base.diagnose_tcr_ecs()["tcr"] == mock_tcr_val
    assert mock_diagnose_tcr_ecs_setup.call_count == 1
    mock_run.assert_called_with(
        only=["CO2_CONC", "TOTAL_INCLVOLCANIC_RF", "SURFACE_TEMP"]
    )
    assert mock_get_tcr_ecs_from_results.call_count == 1
    mock_get_tcr_ecs_from_results.assert_called_with(mock_run())

    assert magicc_base.diagnose_tcr_ecs()["ecs"] == mock_ecs_val
    assert mock_diagnose_tcr_ecs_setup.call_count == 2
    assert mock_get_tcr_ecs_from_results.call_count == 2

    full_results = magicc_base.diagnose_tcr_ecs()
    assert isinstance(full_results, dict)


@pytest.fixture
def valid_tcr_ecs_diagnosis_results():
    startyear = 1700
    endyear = 4000
    spin_up_time = 50
    rising_time = 70
    tcr_yr = startyear + spin_up_time + rising_time
    ecs_yr = endyear
    fake_PI_conc = 278.0
    eqm_time = endyear - startyear - spin_up_time - rising_time

    fake_time = np.arange(startyear, endyear + 1)
    fake_concs = np.concatenate(
        (
            fake_PI_conc * np.ones(spin_up_time),
            fake_PI_conc * 1.01 ** (np.arange(rising_time + 1)),
            fake_PI_conc * 1.01 ** (rising_time) * np.ones(eqm_time),
        )
    )
    fake_rf = 2.0 * np.log(fake_concs / fake_PI_conc)
    fake_temp = np.log(fake_rf + 1.0) + fake_time / fake_time[1400]

    mock_results = {}
    mock_results["CO2_CONC"] = pd.DataFrame({"GLOBAL": fake_concs}, index=fake_time)
    mock_results["TOTAL_INCLVOLCANIC_RF"] = pd.DataFrame(
        {"GLOBAL": fake_rf}, index=fake_time
    )
    mock_results["SURFACE_TEMP"] = pd.DataFrame({"GLOBAL": fake_temp}, index=fake_time)
    yield {"mock_results": mock_results, "tcr_yr": tcr_yr, "ecs_yr": ecs_yr}


@patch.object(MAGICCBase, "_check_tcr_ecs_temp")
@patch.object(MAGICCBase, "_check_tcr_ecs_total_RF")
@patch.object(MAGICCBase, "_get_tcr_ecs_yr_from_CO2_concs")
def test_get_tcr_ecs_from_diagnosis_results(
    mock_get_tcr_ecs_yr_from_CO2_concs,
    mock_check_tcr_ecs_total_RF,
    mock_check_tcr_ecs_temp,
    valid_tcr_ecs_diagnosis_results,
    magicc_base,
):
    test_tcr_yr = valid_tcr_ecs_diagnosis_results["tcr_yr"]
    test_ecs_yr = valid_tcr_ecs_diagnosis_results["ecs_yr"]
    test_results_dict = valid_tcr_ecs_diagnosis_results["mock_results"]

    mock_get_tcr_ecs_yr_from_CO2_concs.return_value = [test_tcr_yr, test_ecs_yr]

    expected_tcr = test_results_dict["SURFACE_TEMP"]["GLOBAL"].loc[test_tcr_yr]
    expected_ecs = test_results_dict["SURFACE_TEMP"]["GLOBAL"].loc[test_ecs_yr]

    actual_tcr, actual_ecs = magicc_base._get_tcr_ecs_from_diagnosis_results(
        test_results_dict
    )
    assert actual_tcr == expected_tcr
    assert actual_ecs == expected_ecs

    mock_get_tcr_ecs_yr_from_CO2_concs.assert_called_with(
        test_results_dict["CO2_CONC"]["GLOBAL"]
    )
    mock_check_tcr_ecs_total_RF.assert_called_with(
        test_results_dict["TOTAL_INCLVOLCANIC_RF"]["GLOBAL"],
        tcr_yr=test_tcr_yr,
        ecs_yr=test_ecs_yr,
    )
    mock_check_tcr_ecs_temp.assert_called_with(
        test_results_dict["SURFACE_TEMP"]["GLOBAL"]
    )


def test_get_tcr_ecs_yr_from_CO2_concs(valid_tcr_ecs_diagnosis_results, magicc_base):
    test_CO2_data = valid_tcr_ecs_diagnosis_results["mock_results"]["CO2_CONC"][
        "GLOBAL"
    ]
    actual_tcr_yr, actual_ecs_yr = magicc_base._get_tcr_ecs_yr_from_CO2_concs(
        test_CO2_data
    )
    assert actual_tcr_yr == valid_tcr_ecs_diagnosis_results["tcr_yr"]
    assert actual_ecs_yr == valid_tcr_ecs_diagnosis_results["ecs_yr"]

    test_time = test_CO2_data.index.values
    for year_to_break in [
        test_time[0],
        test_time[15],
        test_time[115],
        test_time[-1] - 100,
        test_time[-1],
    ]:
        broken_CO2_data = test_CO2_data.copy()
        broken_CO2_data.loc[year_to_break] = test_CO2_data.loc[year_to_break] * 1.01
        with pytest.raises(ValueError, match=r"The TCR/ECS CO2 concs look wrong.*"):
            magicc_base._get_tcr_ecs_yr_from_CO2_concs(broken_CO2_data)


def test_check_tcr_ecs_total_RF(valid_tcr_ecs_diagnosis_results, magicc_base):
    test_RF_data = valid_tcr_ecs_diagnosis_results["mock_results"][
        "TOTAL_INCLVOLCANIC_RF"
    ]["GLOBAL"]
    magicc_base._check_tcr_ecs_total_RF(
        test_RF_data,
        valid_tcr_ecs_diagnosis_results["tcr_yr"],
        valid_tcr_ecs_diagnosis_results["ecs_yr"],
    )
    test_time = test_RF_data.index.values
    for year_to_break in [
        test_time[0],
        test_time[15],
        test_time[115],
        test_time[-1] - 100,
        test_time[-1],
    ]:
        broken_CO2_data = test_RF_data.copy()
        broken_CO2_data.loc[year_to_break] = (
            test_RF_data.loc[year_to_break] * 1.01 + 0.01
        )
        with pytest.raises(
            ValueError, match=r"The TCR/ECS total radiative forcing looks wrong.*"
        ):
            magicc_base._check_tcr_ecs_total_RF(
                broken_CO2_data,
                valid_tcr_ecs_diagnosis_results["tcr_yr"],
                valid_tcr_ecs_diagnosis_results["ecs_yr"],
            )


def test_check_tcr_ecs_temp(valid_tcr_ecs_diagnosis_results, magicc_base):
    test_temp_data = valid_tcr_ecs_diagnosis_results["mock_results"]["SURFACE_TEMP"][
        "GLOBAL"
    ]
    magicc_base._check_tcr_ecs_temp(test_temp_data)

    test_time = test_temp_data.index.values
    for year_to_break in [
        test_time[3],
        test_time[15],
        test_time[115],
        test_time[-1] - 100,
        test_time[-1],
    ]:
        broken_temp_data = test_temp_data.copy()
        broken_temp_data.loc[year_to_break] = (
            test_temp_data.loc[year_to_break - 1] - 0.1
        )
        with pytest.raises(
            ValueError,
            match=r"The TCR/ECS surface temperature looks wrong, it decreases",
        ):
            magicc_base._check_tcr_ecs_temp(broken_temp_data)


# integration test (i.e. actually runs magicc) hence slow
@pytest.mark.slow
def test_integration_diagnose_tcr_ecs(package):
    actual_result = package.diagnose_tcr_ecs()
    assert isinstance(actual_result, dict)
    assert "tcr" in actual_result
    assert "ecs" in actual_result
    assert actual_result["tcr"] < actual_result["ecs"]
    if isinstance(package, MAGICC6):
        # MAGICC6 shipped with pymagicc should be stable
        np.testing.assert_allclose(actual_result["tcr"], 1.9733976)
        np.testing.assert_allclose(actual_result["ecs"], 2.9968448)


def test_read_parameters():
    with MAGICC6() as magicc:
        # parameters don't exist
        with pytest.raises(FileNotFoundError):
            magicc.read_parameters()

        # Don't read config if it doesn't exist
        magicc.set_config(out_parameters=0)
        magicc.run()

        assert magicc.config is None

    with MAGICC6() as magicc:
        magicc.run()
        assert isinstance(magicc.config, dict)
        assert "allcfgs" in magicc.config


def test_updates_namelist(package):
    write_config(package)

    fname = join(package.run_dir, "MAGTUNE_SIMPLE.CFG")
    raw_conf = f90nml.read(fname)
    assert "test_value" not in raw_conf["nml_allcfgs"]

    package.update_config("MAGTUNE_SIMPLE.CFG", test_value=1.2)

    updated_conf = f90nml.read(fname)
    assert "test_value" in updated_conf["nml_allcfgs"]


def test_updates_namelist_missing(package):
    fname = join(package.run_dir, "MAGTUNE_NOTEXISTS.CFG")

    assert not exists(fname)

    package.update_config("MAGTUNE_NOTEXISTS.CFG", test_value=1.2)

    updated_conf = f90nml.read(fname)
    assert "test_value" in updated_conf["nml_allcfgs"]


def test_ascii_output(package):
    fname = join(package.run_dir, "MAGTUNE_PYMAGICC.CFG")

    package.set_output_variables(write_ascii=True, write_binary=True)
    raw_conf = f90nml.read(fname)
    assert raw_conf["nml_allcfgs"]["OUT_ASCII_BINARY"] == "BOTH"

    package.set_output_variables(write_ascii=False, write_binary=True)
    raw_conf = f90nml.read(fname)
    assert raw_conf["nml_allcfgs"]["OUT_ASCII_BINARY"] == "BINARY"

    package.set_output_variables()
    raw_conf = f90nml.read(fname)
    assert raw_conf["nml_allcfgs"]["OUT_ASCII_BINARY"] == "ASCII"

    with pytest.raises(AssertionError):
        package.set_output_variables(write_ascii=False, write_binary=False)


def test_output_variables(package):
    fname = join(package.run_dir, "MAGTUNE_PYMAGICC.CFG")

    package.set_output_variables()
    raw_conf = f90nml.read(fname)
    assert raw_conf["nml_allcfgs"]["OUT_TEMPERATURE"] == 0

    package.set_output_variables(temperature=True)
    raw_conf = f90nml.read(fname)
    assert raw_conf["nml_allcfgs"]["OUT_TEMPERATURE"] == 1

    # Even accepts invalid variable names
    package.set_output_variables(this_doesnt_exist=False)
    raw_conf = f90nml.read(fname)
    assert raw_conf["nml_allcfgs"]["OUT_THIS_DOESNT_EXIST"] == 0


def test_persistant_state(package):
    test_ecs = 1.75
    package.update_config(CORE_CLIMATESENSITIVITY=test_ecs)
    actual_results = package.diagnose_tcr_ecs()
    np.testing.assert_allclose(actual_results["ecs"], test_ecs, rtol=1e-02)


# TODO: move to integration tests folder
@pytest.mark.parametrize(
    "test_filename, relevant_config, outputs_to_check, time_check_min, time_check_max",
    [
        (
            "HISTRCP_N2OI_EMIS.IN",
            {
                "file_n2oi_emis": "test_filename",
                "out_emissions": 1,
                "scen_histadjust_0no1scale2shift": 0,
            },
            ["N2OI_EMIS"],
            1,
            1999,
        ),
        (
            "HISTRCP_CH4_CONC.IN",
            {"file_ch4_conc": "test_filename"},
            ["CH4_CONC"],
            1,
            1999,
        ),
        (
            "RCP26.SCEN",
            {
                "file_emissionscenario": "test_filename",
                "out_emissions": 1,
                "scen_histadjust_0no1scale2shift": 0,
            },
            ["CO2I_EMIS", "CO2B_EMIS", "CH4_EMIS", "BC_EMIS", "SOX_EMIS", "HFC32_EMIS"],
            2030,
            20000,
        ),
        (
            "SRESA2.SCEN",
            {
                "file_emissionscenario": "test_filename",
                "out_emissions": 1,
                "scen_histadjust_0no1scale2shift": 0,
            },
            ["CO2I_EMIS", "CO2B_EMIS", "CH4_EMIS", "BC_EMIS", "SOX_EMIS", "HFC32_EMIS"],
            2030,
            20000,
        ),
    ],
)
def test_pymagicc_writing_compatibility(
    package,
    test_filename,
    relevant_config,
    outputs_to_check,
    time_check_min,
    time_check_max,
):
    for key, value in relevant_config.items():
        if value == "test_filename":
            relevant_config[key] = test_filename

    package.set_config(**relevant_config)
    initial_results = package.run()

    ttweak_factor = 0.9

    mdata = MAGICCData(filename=test_filename)
    mdata.read(package.run_dir)
    mdata.df.value *= ttweak_factor
    mdata.write(test_filename, package.run_dir, magicc_version=package.version)
    if test_filename.endswith("SCEN"):
        import pdb

        pdb.set_trace()

    tweaked_results = package.run()

    for output_to_check in outputs_to_check:
        result = (
            tweaked_results[output_to_check]["GLOBAL"]
            .loc[time_check_min:time_check_max]
            .values
        )
        expected = (
            ttweak_factor
            * initial_results[output_to_check]["GLOBAL"]
            .loc[time_check_min:time_check_max]
            .values
        )
        np.testing.assert_allclose(result, expected, rtol=1e-5)
