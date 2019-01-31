from os import remove, environ
from os.path import exists, join
from datetime import datetime
from dateutil.relativedelta import relativedelta
from subprocess import CalledProcessError
from unittest.mock import patch
import re
import copy


import numpy as np
import pytest
import pandas as pd
import f90nml


from pymagicc import MAGICC6, MAGICC7, rcp26
from pymagicc.core import MAGICCBase, config, _clean_value
from pymagicc.io import MAGICCData
from .test_config import config_override  #  noqa
from .conftest import MAGICC6_DIR, TEST_DATA_DIR


@pytest.fixture(scope="function")
def magicc_base():
    yield MAGICCBase()


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
    if exists(join(package.run_dir, "HISTRCP_CO2I_EMIS.IN")):
        remove(join(package.run_dir, "HISTRCP_CO2I_EMIS.IN"))

    if exists(join(package.run_dir, "HISTSSP_CO2I_EMIS.IN")):
        remove(join(package.run_dir, "HISTSSP_CO2I_EMIS.IN"))

    with pytest.raises(CalledProcessError):
        package.run()

    assert package.config is None


def test_run_failure_no_magcfg_user(package):
    if exists(join(package.run_dir, "MAGCFG_USER.CFG")):
        remove(join(package.run_dir, "MAGCFG_USER.CFG"))

    with pytest.raises(FileNotFoundError):
        package.run()

    assert package.config is None


@pytest.mark.parametrize(
    "invalid_config",
    [
        {"nml_allcfgs": {"file_tuningmodel_1": "junk"}},
        {
            "nml_allcfgs": {
                "file_tuningmodel_1": "pymagicc",
                "file_tuningmodel_2": "pymagicc",
            }
        },
        {
            "nml_allcfgs": {
                "file_tuningmodel_1": "pymagicc",
                "file_tuningmodel_2": "c4mip_default",
            }
        },
        {
            "nml_allcfgs": {
                "file_tuningmodel_1": "c4mip_default",
                "file_tuningmodel_2": "pymagicc",
            }
        },
    ],
)
def test_run_failure_no_pymagicc_in_magcfg_user(package, invalid_config):
    f90nml.write(invalid_config, join(package.run_dir, "MAGCFG_USER.CFG"), force=True)

    error_msg = re.escape(
        "PYMAGICC is not the only tuning model that will be used by "
        "`MAGCFG_USER.CFG`: your run is likely to fail/do odd things"
    )
    with pytest.raises(ValueError, match=error_msg):
        package.run()

    assert package.config is None


@pytest.mark.parametrize(
    "invalid_config",
    [
        {"nml_allcfgs": {"file_emisscen": "SSP1", "file_emisscen_2": "SSP2"}},
        {
            "nml_allcfgs": {
                "file_emisscen": "SSP1",
                "file_emisscen_2": "",
                "file_emisscen_3": "SSP2",
            }
        },
        {
            "nml_allcfgs": {
                "file_emisscen": "",
                "file_emisscen_2": "SSP1",
                "file_emisscen_3": "SSP2",
            }
        },
    ],
)
def test_run_failure_confusing_emissions_scenarios(package, invalid_config):
    f90nml.write(invalid_config, join(package.run_dir, "MAGCFG_USER.CFG"), force=True)

    error_msg = re.escape(
        "You have more than one `FILE_EMISSCEN_X` flag set. Using more than one "
        "emissions scenario is hard to debug and unnecessary with Pymagicc's "
        "dataframe scenario input. Please combine all your scenarios into one "
        "dataframe with Pymagicc and pandas, then feed this single Dataframe into "
        "Pymagicc's run API."
    )
    with pytest.raises(ValueError, match=error_msg):
        package.run()

    assert package.config is None


def test_run_success(package):
    write_config(package)
    results = package.run(out_parameters=1)

    assert isinstance(results, MAGICCData)
    assert len(results["variable"].unique()) > 1
    assert "Surface Temperature" in results["variable"].values

    assert (results["climate_model"] == "MAGICC{}".format(package.version)).all()
    # running with preset information should result in unspecified everywhere
    # only running from an IamDataFrame instance should automatically fill model
    # and scenario columns
    assert (results["model"] == "unspecified").all()
    assert (results["scenario"] == "unspecified").all()

    assert len(package.config.keys()) != 0


def test_run_with_magiccdata(package, temp_dir):
    tmodel = "IMAGE"
    tscenario = "RCP26"
    scen = MAGICCData(join(MAGICC6_DIR, "RCP26.SCEN"), model=tmodel, scenario=tscenario)

    results = package.run(scen, only=["Surface Temperature"])

    assert len(results["variable"].unique()) == 1
    assert "Surface Temperature" in results["variable"].values

    assert (results["climate_model"] == "MAGICC{}".format(package.version)).all()
    assert (results["model"] == tmodel).all()
    assert (results["scenario"] == tscenario).all()


def test_run_success_binary(package):
    results = package.run(out_ascii_binary="BINARY", out_keydata_2=True)

    assert isinstance(results, MAGICCData)
    assert len(results["variable"].unique()) > 1
    assert "Surface Temperature" in results["variable"].values

    assert len(package.config.keys()) != 0


def test_run_success_update_config(package):
    package.set_output_variables(
        keydata_2=True, parameters=1, write_ascii=False, write_binary=True
    )
    results = package.run()

    assert isinstance(results, MAGICCData)
    assert len(results["variable"].unique()) > 1
    assert "Surface Temperature" in results["variable"].values

    assert len(package.config.keys()) != 0


def test_run_only(package):
    write_config(package)
    results = package.run(only=["Surface Temperature"])

    assert len(results["variable"].unique()) == 1
    assert "Surface Temperature" in results["variable"].values


def test_run_rewritten_scen_file(package, temp_dir):
    starting_scen = join(MAGICC6_DIR, "RCP26.SCEN")
    written_scen = join(package.run_dir, "RCP26.SCEN7")

    mdata_initial = MAGICCData(starting_scen)

    mdata_initial.write(written_scen, magicc_version=7)

    mdata_written = MAGICCData(written_scen)

    results = package.run(mdata_written, only=["Surface Temperature"])

    assert len(results["variable"].unique()) == 1
    assert "Surface Temperature" in results["variable"].values


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
    fake_regions = ["World"] * len(fake_time)

    mock_co2_conc = pd.DataFrame(
        {
            "time": fake_time,
            "unit": ["ppm"] * len(fake_time),
            "variable": ["Atmospheric Concentrations|CO2"] * len(fake_time),
            "value": fake_concs,
            "region": fake_regions,
            "model": ["N/A"] * len(fake_time),
            "scenario": ["1%/yr_co2"] * len(fake_time),
        }
    )
    mock_rf = pd.DataFrame(
        {
            "time": fake_time,
            "unit": ["W / m^2"] * len(fake_time),
            "variable": ["Radiative Forcing"] * len(fake_time),
            "value": fake_rf,
            "region": fake_regions,
            "model": ["N/A"] * len(fake_time),
            "scenario": ["1%/yr_co2"] * len(fake_time),
        }
    )
    mock_temp = pd.DataFrame(
        {
            "time": fake_time,
            "unit": ["K"] * len(fake_time),
            "variable": ["Surface Temperature"] * len(fake_time),
            "value": fake_temp,
            "region": fake_regions,
            "model": ["N/A"] * len(fake_time),
            "scenario": ["1%/yr_co2"] * len(fake_time),
        }
    )
    mock_results = MAGICCData(pd.concat([mock_co2_conc, mock_rf, mock_temp]))

    yield {
        "mock_results": mock_results,
        "tcr_time": datetime(tcr_yr, 1, 1),
        "ecs_time": datetime(ecs_yr, 1, 1),
    }


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
    test_tcr_time = valid_tcr_ecs_diagnosis_results["tcr_time"]
    test_ecs_time = valid_tcr_ecs_diagnosis_results["ecs_time"]
    test_results_df = valid_tcr_ecs_diagnosis_results["mock_results"]

    mock_get_tcr_ecs_yr_from_CO2_concs.return_value = [test_tcr_time, test_ecs_time]

    expected_tcr = (
        test_results_df.filter(variable="Surface Temperature", time=test_tcr_time)
        .timeseries()
        .squeeze()
    )
    expected_ecs = (
        test_results_df.filter(variable="Surface Temperature", time=test_ecs_time)
        .timeseries()
        .squeeze()
    )

    actual_tcr, actual_ecs = magicc_base._get_tcr_ecs_from_diagnosis_results(
        test_results_df
    )
    assert actual_tcr == expected_tcr
    assert actual_ecs == expected_ecs

    assert mock_get_tcr_ecs_yr_from_CO2_concs.call_count == 1
    assert mock_check_tcr_ecs_total_RF.call_count == 1
    assert mock_check_tcr_ecs_temp.call_count == 1


def assert_bad_tcr_ecs_diagnosis_values_caught(
    base_data, method_to_run, regexp_to_match, *args, test_target="other"
):
    test_time = base_data["time"].values
    times_to_break = [
        test_time[3],
        test_time[15],
        test_time[115],
        test_time[-100],
        test_time[-1],
    ]
    if test_target != "temperature":
        times_to_break.append(test_time[0])
    for time_to_break in times_to_break:
        broken_data = copy.deepcopy(base_data)
        row_to_adjust = broken_data.data.time == time_to_break
        if test_target == "temperature":
            broken_data.data.loc[row_to_adjust, "value"] -= 0.1
        else:
            broken_data.data.loc[row_to_adjust, "value"] *= 1.01
            broken_data.data.loc[row_to_adjust, "value"] += 0.01
        with pytest.raises(ValueError, match=regexp_to_match):
            method_to_run(broken_data, *args)


def test_get_tcr_ecs_yr_from_CO2_concs(valid_tcr_ecs_diagnosis_results, magicc_base):
    test_results_df = valid_tcr_ecs_diagnosis_results["mock_results"]
    test_CO2_data = test_results_df.filter(
        variable="Atmospheric Concentrations|CO2"
    ).to_iamdataframe()

    actual_tcr_yr, actual_ecs_yr = magicc_base._get_tcr_ecs_yr_from_CO2_concs(
        test_CO2_data
    )
    assert actual_tcr_yr == valid_tcr_ecs_diagnosis_results["tcr_time"]
    assert actual_ecs_yr == valid_tcr_ecs_diagnosis_results["ecs_time"]

    assert_bad_tcr_ecs_diagnosis_values_caught(
        test_CO2_data,
        magicc_base._get_tcr_ecs_yr_from_CO2_concs,
        r"The TCR/ECS CO2 concs look wrong.*",
    )


def test_check_tcr_ecs_total_RF(valid_tcr_ecs_diagnosis_results, magicc_base):
    test_results_df = valid_tcr_ecs_diagnosis_results["mock_results"]
    test_RF_data = test_results_df.filter(
        variable="Radiative Forcing"
    ).to_iamdataframe()
    magicc_base._check_tcr_ecs_total_RF(
        test_RF_data,
        valid_tcr_ecs_diagnosis_results["tcr_time"],
        valid_tcr_ecs_diagnosis_results["ecs_time"],
    )

    assert_bad_tcr_ecs_diagnosis_values_caught(
        test_RF_data,
        magicc_base._check_tcr_ecs_total_RF,
        r"The TCR/ECS total radiative forcing looks wrong.*",
        valid_tcr_ecs_diagnosis_results["tcr_time"],
        valid_tcr_ecs_diagnosis_results["ecs_time"],
    )


def test_check_tcr_ecs_temp(valid_tcr_ecs_diagnosis_results, magicc_base):
    test_results_df = valid_tcr_ecs_diagnosis_results["mock_results"]
    test_temp_data = test_results_df.filter(
        variable="Surface Temperature"
    ).to_iamdataframe()

    magicc_base._check_tcr_ecs_temp(test_temp_data)

    assert_bad_tcr_ecs_diagnosis_values_caught(
        test_temp_data,
        magicc_base._check_tcr_ecs_temp,
        r"The TCR/ECS surface temperature looks wrong, it decreases",
        test_target="temperature",
    )


# integration test (i.e. actually runs magicc) hence slow
@pytest.mark.slow
def test_integration_diagnose_tcr_ecs(package):
    if package.version == 7:
        pytest.xfail(reason="MAGICC7 TCR/ECS diagnosis is currently broken")
        package.diagnose_tcr_ecs()

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
    mock_get_tcr_ecs_from_results,
    mock_run,
    mock_diagnose_tcr_ecs_setup,
    magicc_base,
    valid_tcr_ecs_diagnosis_results,
):
    mock_tcr_val = 1.8
    mock_ecs_val = 3.1
    mock_run_results = valid_tcr_ecs_diagnosis_results

    mock_run.return_value = mock_run_results
    mock_get_tcr_ecs_from_results.return_value = [mock_tcr_val, mock_ecs_val]

    assert magicc_base.diagnose_tcr_ecs()["tcr"] == mock_tcr_val
    assert mock_diagnose_tcr_ecs_setup.call_count == 1
    mock_run.assert_called_with(
        only=[
            "Atmospheric Concentrations|CO2",
            "Radiative Forcing",
            "Surface Temperature",
        ],
        scenario=None,
    )
    assert mock_get_tcr_ecs_from_results.call_count == 1
    assert mock_get_tcr_ecs_from_results.call_count == 1

    assert magicc_base.diagnose_tcr_ecs()["ecs"] == mock_ecs_val
    assert mock_diagnose_tcr_ecs_setup.call_count == 2
    assert mock_get_tcr_ecs_from_results.call_count == 2

    full_results = magicc_base.diagnose_tcr_ecs()
    assert isinstance(full_results, dict)


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
    test_ecs = 4.3
    package.update_config(CORE_CLIMATESENSITIVITY=test_ecs)
    actual_results = package.run(out_parameters=1)
    assert (
        actual_results.metadata["parameters"]["allcfgs"]["core_climatesensitivity"]
        == test_ecs
    )


def test_persistant_state_integration(package):
    if package.version == 7:
        pytest.xfail(reason="MAGICC7 TCR/ECS diagnosis is currently broken")
        package.diagnose_tcr_ecs()
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
            ["Emissions|N2O|MAGICC Fossil and Industrial"],
            1,
            1999,
        ),
        (
            "HISTRCP_CH4_CONC.IN",
            {"file_ch4_conc": "test_filename", "out_concentrations": 1},
            ["Atmospheric Concentrations|CH4"],
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
            [
                "Emissions|CO2|MAGICC Fossil and Industrial",
                "Emissions|CO2|MAGICC AFOLU",
                "Emissions|CH4|MAGICC Fossil and Industrial",
                "Emissions|BC|MAGICC Fossil and Industrial",
                "Emissions|SOx|MAGICC AFOLU",
                "Emissions|HFC32",
            ],
            2030,
            20000,
        ),
        (
            "RCP26.SCEN7",
            {
                "file_emissionscenario": "test_filename",
                "out_emissions": 1,
                "scen_histadjust_0no1scale2shift": 0,
            },
            [
                "Emissions|CO2|MAGICC Fossil and Industrial",
                "Emissions|CO2|MAGICC AFOLU",
                "Emissions|CH4|MAGICC Fossil and Industrial",
                "Emissions|BC|MAGICC Fossil and Industrial",
                "Emissions|SOx|MAGICC AFOLU",
                "Emissions|HFC32",
            ],
            2030,
            20000,
        ),
        (
            "SRESA2.SCEN",  # all other SRES scenarios have been removed from MAGICC7's run directory
            {
                "file_emisscen": "test_filename",  # use MAGICC7 flag here, should still pass
                "out_emissions": 1,
                "scen_histadjust_0no1scale2shift": 0,
            },
            [
                "Emissions|CO2|MAGICC Fossil and Industrial",
                "Emissions|CO2|MAGICC AFOLU",
                "Emissions|CH4|MAGICC Fossil and Industrial",
                "Emissions|SOx|MAGICC AFOLU",
                "Emissions|HFC32",
            ],
            2030,
            20000,
        ),
    ],
)
def test_pymagicc_writing_has_an_effect(
    package,
    test_filename,
    relevant_config,
    outputs_to_check,
    time_check_min,
    time_check_max,
):
    if (package.version == 6) and test_filename.endswith("SCEN7"):
        # maybe this should throw error instead
        pytest.skip("MAGICC6 cannot run SCEN7 files")
    if ("SRES" in test_filename) and (package.version == 7):
        # maybe this should throw error instead
        pytest.skip("MAGICC7 cannot run SRES SCEN files")
    if ("SCEN" in test_filename) and (package.version == 7):
        # special undocumented flags!!!
        relevant_config["fgas_adjstfutremis2past_0no1scale"] = 0
        relevant_config["mhalo_adjstfutremis2past_0no1scale"] = 0

    for key, value in relevant_config.items():
        if value == "test_filename":
            relevant_config[key] = test_filename

    package.set_config(**relevant_config)
    initial_results = package.run()

    ttweak_factor = 0.9

    mdata = MAGICCData(join(package.run_dir, test_filename))
    mdata._data *= ttweak_factor
    mdata.write(join(package.run_dir, test_filename), package.version)

    tweaked_results = package.run()

    for output_to_check in outputs_to_check:
        result = (
            tweaked_results.filter(
                variable=output_to_check, year=range(time_check_min, time_check_max + 1)
            )
            .timeseries()
            .values
        )
        expected = (
            ttweak_factor
            * initial_results.filter(
                variable=output_to_check, year=range(time_check_min, time_check_max + 1)
            )
            .timeseries()
            .values
        )
        abstol = np.max([result, expected]) * 10 ** -3
        np.testing.assert_allclose(result, expected, rtol=1e-5, atol=abstol)


# TODO: move to integration tests folder
@pytest.mark.parametrize(
    "test_filename, relevant_config, outputs_to_check",
    [
        (
            "RCP26.SCEN",
            {
                "file_emissionscenario": "test_filename",
                "out_emissions": 1,
                "scen_histadjust_0no1scale2shift": 0,
            },
            [("Emissions|C2F6", "World", 2050, "kt C2F6 / yr", 0.4712)],
        )
    ],
)
def test_pymagicc_writing_compatibility_203(
    package, test_filename, relevant_config, outputs_to_check
):
    if ("SCEN" in test_filename) and (package.version == 7):
        # special undocumented flags!!!
        relevant_config["fgas_adjstfutremis2past_0no1scale"] = 0
        relevant_config["mhalo_adjstfutremis2past_0no1scale"] = 0

    for key, value in relevant_config.items():
        if value == "test_filename":
            relevant_config[key] = test_filename

    package.set_config(**relevant_config)
    results = package.run()

    for output_to_check in outputs_to_check:
        expected = output_to_check[-1]
        result = (
            results.filter(
                variable=output_to_check[0],
                region=output_to_check[1],
                year=output_to_check[2],
                unit=output_to_check[3],
            )
            .timeseries()
            .squeeze()
        )

        assert expected == result


@pytest.mark.parametrize("emms_co2_level", [0, 5])
def test_co2_emms_other_rf_run(package, emms_co2_level):
    # TODO: add blank scenario dataframe so users can actually zero things sensibly

    base = MAGICCData(join(TEST_DATA_DIR, "RCP3PD_EMISSIONS.DAT"))
    emms_df = base.filter(region="World").data.copy()
    emms_df.loc[:, "value"] = 0

    time = emms_df.loc[
        emms_df["variable"] == "Emissions|CO2|MAGICC Fossil and Industrial",
        "time"
    ]

    # forcing_external = 2.0 * np.arange(0, len(time)) / len(time)
    # line below gives you zero run
    forcing_external = 0.0 * np.arange(0, len(time)) / len(time)
    forcing_external_df = pd.DataFrame({
        "time": time,
        "scenario": "idealised",
        "model": "unspecified",
        "climate_model": "unspecified",
        "variable": "Radiative Forcing|Extra",
        "unit": "W / m^2",
        "todo": "SET",
        "region": "World",
        "value": forcing_external
    })
    forcing_ext = MAGICCData(forcing_external_df)
    forcing_ext_filename = "EXTERNAL_RF.IN"
    forcing_ext.metadata = {"header": "External radiative forcing file for testing"}
    forcing_ext.write(join(package.run_dir, forcing_ext_filename), package.version)


    ch4_conc = 721.894107 * np.ones(len(time))
    ch4_conc_df = pd.DataFrame({
        "time": time,
        "scenario": "idealised",
        "model": "unspecified",
        "climate_model": "unspecified",
        "variable": "Atmospheric Concentrations|CH4",
        "unit": "ppb",
        "todo": "SET",
        "region": "World",
        "value": ch4_conc
    })
    ch4_c = MAGICCData(ch4_conc_df)
    ch4_c_filename = "HIST_ZERO_CH4_CONC.IN"
    ch4_c.metadata = {"header": "Zero CH4 concentrations file for testing"}
    ch4_c.write(join(package.run_dir, ch4_c_filename), package.version)

    emms_co2 = np.zeros(len(time))
    jump_idx = 250
    emms_co2[jump_idx:] = emms_co2_level

    emms_df.loc[
        emms_df["variable"] == "Emissions|CO2|MAGICC Fossil and Industrial",
        "value"
    ] = emms_co2
    emms_df["scenario"] = "idealised"
    emms_df["model"] = "unspecified"

    scen = MAGICCData(emms_df)
    # results = package.run(scen, startyear=2050)  # startyear does not work...
    results = package.run(
        scen,
        scen_histadjust_0no1scale2shift=1,
        endyear=2500,
        rf_extra_read=1,  # fix writing of 'True'
        file_extra_rf=forcing_ext_filename,
        rf_total_runmodus="all",
        rf_preind_referenceyr=time.min().year,
        rf_initialization_method="ZEROSTARTSHIFT",
        rf_total_constantafteryr=5000,
        file_co2i_emis="",
        file_co2b_emis="",
        file_ch4i_emis="",
        file_ch4b_emis="",
        file_ch4n_emis="",
        file_ch4_conc=ch4_c_filename,
        file_n2oi_emis="",
        file_n2ob_emis="",
        file_n2on_emis="",
        file_n2o_conc="",
        file_noxi_emis="",
        file_noxb_emis="",
        file_noxi_ot="",
        file_noxb_ot="",
        file_noxt_rf="",
        file_nh3i_emis="",
        file_nh3b_emis="",
        file_nmvoci_emis="",
        file_nmvocb_emis="",
        file_mineraldust_rf="",
        file_landuse_rf="",
        file_soxnb_ot="",
        file_soxi_ot="",
        file_soxt_rf="",
        file_soxi_emis="",
        file_soxb_emis="",
        file_soxn_emis="",
        file_coi_emis="",
        file_cob_emis="",
        file_bci_emis="",
        file_bcb_emis="",
        file_bci_ot="",
        file_bcb_ot="",
        file_bci_rf="",
        file_bcb_rf="",
        file_oci_emis="",
        file_ocb_emis="",
        file_oci_ot="",
        file_ocb_ot="",
        file_oci_rf="",
        file_ocb_rf="",
        file_bcsnow_rf="",
        rf_volcanic_scale=0,
        rf_solar_scale=0,
        rf_fgassum_scale=0,  # this appears to do nothing
        rf_mhalosum_scale=0,
        stratoz_o3scale=0,
        fgas_switchfromconc2emis_year=10000,
        file_fgas_conc=[ch4_c_filename]*12,
        mhalo_switch_conc2emis_yr=1750,
        co2_switchfromconc2emis_year=1750,
        ch4_switchfromconc2emis_year=10000,
        n2o_switchfromconc2emis_year=1750,
        bcoc_switchfromrf2emis_year=1750,
        out_forcing=1,
        out_ascii_binary="ASCII",
        only=["Emissions|CO2|MAGICC Fossil and Industrial", "Radiative Forcing"]
    )  # startyear does not work...
    # TODO: fix endyear so it takes from scenario input by default

    np.testing.assert_allclose(
        results.filter(variable="Em*CO2*Fossil*", region="World")["value"],
        emms_co2
    )
    # CO2 temperature feedbacks mean that you get a CO2 outgassing, hence CO2 forcing
    # and hence values don't match exactly. Numerical precision adds to this
    greater_equal_rows = (
        results.filter(variable="Radiative Forcing", region="World")["value"]
        >= forcing_external
    )
    close_rows = (
        np.abs(
            results.filter(variable="Radiative Forcing", region="World")["value"]
            - forcing_external
        ) / forcing_external <= 10**-3
    )
    matching_rows = greater_equal_rows | close_rows
    assert matching_rows.all()

    # desired_precision = 2  # decimal places
    # good_rows = np.round(results.filter(variable="Radiative Forcing", region="World")["value"], desired_precision) >= np.round(forcing_external, desired_precision)
    # results.filter(variable="Radiative Forcing", region="World")[~good_rows]
    # assert (
    #     np.round(results.filter(variable="Radiative Forcing", region="World")["value"], 5) >= np.round(forcing_external, 5)
    #     results.filter(variable="Radiative Forcing", region="World")["value"] >= forcing_external
    # ).all()
    # if emms_co2_level == 0:
    #     np.testing.assert_allclose(
    #         results.filter(variable="Radiative Forcing", region="World")["value"],
    #         forcing_external
    #     )
    import pdb
    pdb.set_trace()
    results.variables()
    from pymagicc.definitions import convert_magicc7_to_openscm_variables, convert_magicc6_to_magicc7_variables
    convert_magicc7_to_openscm_variables(convert_magicc6_to_magicc7_variables("MCF_RF"))
    from matplotlib import pyplot as plt; results.filter(variable="Radiative Forcing|CH4", region="World").line_plot(x="time"); plt.show()
    from matplotlib import pyplot as plt; results.filter(variable="Radiative Forcing", region="World").line_plot(x="time"); plt.show()
    from matplotlib import pyplot as plt; results.filter(variable="Radiative Forcing|CO2", region="World").line_plot(x="time"); plt.show()
    from matplotlib import pyplot as plt; results.filter(variable="Em*CO2*Fossil*", region="World").line_plot(x="time"); plt.show()
    from matplotlib import pyplot as plt; results.filter(variable="Em*CO2*AFOL*", region="World").line_plot(x="time"); plt.show()
    from matplotlib import pyplot as plt; results.filter(variable="*Conc*CH4*", region="World").line_plot(x="time"); plt.show()
    from matplotlib import pyplot as plt; results.filter(variable="*Extra*", region="World").line_plot(x="time"); plt.show()
    from matplotlib import pyplot as plt; results.filter(variable="*Temp*", region="World").line_plot(x="time"); plt.show()

