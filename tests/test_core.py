from os import remove, environ
from os.path import exists, join
from subprocess import CalledProcessError
from unittest.mock import patch
import re


import numpy as np
import pytest
import pandas as pd
import f90nml


from pymagicc import MAGICC6, MAGICC7
from pymagicc.core import MAGICCBase, config, _clean_value
from pymagicc.io import MAGICCData
from .test_config import config_override  #  noqa
from .conftest import MAGICC6_DIR


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
    assert len(results.df.variable.unique()) > 1
    assert "Surface Temperature" in results.df.variable.unique()

    assert len(package.config.keys()) != 0


def test_run_success_binary(package):
    results = package.run(out_ascii_binary="BINARY", out_keydata_2=True)

    assert isinstance(results, MAGICCData)
    assert len(results.df.variable.unique()) > 1
    assert "Surface Temperature" in results.df.variable.unique()

    assert len(package.config.keys()) != 0


def test_run_success_update_config(package):
    package.set_output_variables(keydata_2=True, parameters=1, write_ascii=False, write_binary=True)
    results = package.run()

    assert isinstance(results, MAGICCData)
    assert len(results.df.variable.unique()) > 1
    assert "Surface Temperature" in results.df.variable.unique()

    assert len(package.config.keys()) != 0


def test_run_only(package):
    write_config(package)
    results = package.run(only=["Surface Temperature"])

    assert len(results.df.variable.unique()) == 1
    assert "Surface Temperature" in results.df.variable.unique()


def test_run_rewritten_scen_file(package, temp_dir):
    starting_scen = join(MAGICC6_DIR, "RCP26.SCEN")
    written_scen = join(package.run_dir, "RCP26.SCEN7")

    mdata_initial = MAGICCData()
    mdata_initial.read(starting_scen)

    mdata_initial.write(written_scen, magicc_version=7)

    mdata_written = MAGICCData()
    mdata_written.read(written_scen)

    results = package.run(mdata_written, only=["Surface Temperature"])

    assert len(results.df.variable.unique()) == 1
    assert "Surface Temperature" in results.df.variable.unique()


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
    mock_results = MAGICCData()
    mock_results.df = pd.DataFrame()

    mock_run.return_value = mock_results
    mock_get_tcr_ecs_from_results.return_value = [mock_tcr_val, mock_ecs_val]

    assert magicc_base.diagnose_tcr_ecs()["tcr"] == mock_tcr_val
    assert mock_diagnose_tcr_ecs_setup.call_count == 1
    mock_run.assert_called_with(
        scenario=None,
        only=[
            "Atmospheric Concentrations|CO2",
            "Radiative Forcing",
            "Surface Temperature",
        ]
    )
    assert mock_get_tcr_ecs_from_results.call_count == 1
    assert mock_get_tcr_ecs_from_results.call_count == 1

    assert magicc_base.diagnose_tcr_ecs()["ecs"] == mock_ecs_val
    assert mock_diagnose_tcr_ecs_setup.call_count == 2
    assert mock_get_tcr_ecs_from_results.call_count == 2

    full_results = magicc_base.diagnose_tcr_ecs()
    assert isinstance(full_results, dict)


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
        }
    )
    mock_rf = pd.DataFrame(
        {
            "time": fake_time,
            "unit": ["W / m^2"] * len(fake_time),
            "variable": ["Radiative Forcing"] * len(fake_time),
            "value": fake_rf,
            "region": fake_regions,
        }
    )
    mock_temp = pd.DataFrame(
        {
            "time": fake_time,
            "unit": ["K"] * len(fake_time),
            "variable": ["Surface Temperature"] * len(fake_time),
            "value": fake_temp,
            "region": fake_regions,
        }
    )
    mock_results = pd.concat([mock_co2_conc, mock_rf, mock_temp])

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
    test_results_df = valid_tcr_ecs_diagnosis_results["mock_results"]

    mock_get_tcr_ecs_yr_from_CO2_concs.return_value = [test_tcr_yr, test_ecs_yr]

    expected_tcr = test_results_df[
        (test_results_df.variable == "Surface Temperature")
        & (test_results_df.time == test_tcr_yr)
    ].value.values
    expected_ecs = test_results_df[
        (test_results_df.variable == "Surface Temperature")
        & (test_results_df.time == test_ecs_yr)
    ].value.values

    actual_tcr, actual_ecs = magicc_base._get_tcr_ecs_from_diagnosis_results(
        test_results_df
    )
    assert actual_tcr == expected_tcr
    assert actual_ecs == expected_ecs

    assert mock_get_tcr_ecs_yr_from_CO2_concs.call_count == 1
    assert mock_check_tcr_ecs_total_RF.call_count == 1
    assert mock_check_tcr_ecs_temp.call_count == 1


def test_get_tcr_ecs_yr_from_CO2_concs(valid_tcr_ecs_diagnosis_results, magicc_base):
    test_results_df = valid_tcr_ecs_diagnosis_results["mock_results"]
    test_CO2_data = test_results_df[
        test_results_df.variable == "Atmospheric Concentrations|CO2"
    ]

    actual_tcr_yr, actual_ecs_yr = magicc_base._get_tcr_ecs_yr_from_CO2_concs(
        test_CO2_data
    )
    assert actual_tcr_yr == valid_tcr_ecs_diagnosis_results["tcr_yr"]
    assert actual_ecs_yr == valid_tcr_ecs_diagnosis_results["ecs_yr"]

    test_time = test_CO2_data.time.values
    for year_to_break in [
        test_time[0],
        test_time[15],
        test_time[115],
        test_time[-1] - 100,
        test_time[-1],
    ]:
        broken_CO2_data = test_CO2_data.copy()
        broken_CO2_data.loc[broken_CO2_data.time == year_to_break, "value"] *= 1.01
        with pytest.raises(ValueError, match=r"The TCR/ECS CO2 concs look wrong.*"):
            magicc_base._get_tcr_ecs_yr_from_CO2_concs(broken_CO2_data)


def test_check_tcr_ecs_total_RF(valid_tcr_ecs_diagnosis_results, magicc_base):
    test_results_df = valid_tcr_ecs_diagnosis_results["mock_results"]
    test_RF_data = test_results_df[test_results_df.variable == "Radiative Forcing"]
    magicc_base._check_tcr_ecs_total_RF(
        test_RF_data,
        valid_tcr_ecs_diagnosis_results["tcr_yr"],
        valid_tcr_ecs_diagnosis_results["ecs_yr"],
    )
    test_time = test_RF_data.time.values
    for year_to_break in [
        test_time[0],
        test_time[15],
        test_time[115],
        test_time[-1] - 100,
        test_time[-1],
    ]:
        broken_RF_data = test_RF_data.copy()
        broken_RF_data.loc[broken_RF_data.time == year_to_break, "value"] *= 1.01
        broken_RF_data.loc[broken_RF_data.time == year_to_break, "value"] += 1.01
        with pytest.raises(
            ValueError, match=r"The TCR/ECS total radiative forcing looks wrong.*"
        ):
            magicc_base._check_tcr_ecs_total_RF(
                broken_RF_data,
                valid_tcr_ecs_diagnosis_results["tcr_yr"],
                valid_tcr_ecs_diagnosis_results["ecs_yr"],
            )


def test_check_tcr_ecs_temp(valid_tcr_ecs_diagnosis_results, magicc_base):
    test_results_df = valid_tcr_ecs_diagnosis_results["mock_results"]
    test_temp_data = test_results_df[test_results_df.variable == "Surface Temperature"]

    magicc_base._check_tcr_ecs_temp(test_temp_data)

    test_time = test_temp_data.time.values
    for year_to_break in [
        test_time[3],
        test_time[15],
        test_time[115],
        test_time[-1] - 100,
        test_time[-1],
    ]:
        broken_temp_data = test_temp_data.copy()
        broken_temp_data.loc[broken_temp_data.time == year_to_break, "value"] = (
            broken_temp_data.loc[
                broken_temp_data.time == (year_to_break - 1), "value"
            ].values
            - 0.1
        )
        with pytest.raises(
            ValueError,
            match=r"The TCR/ECS surface temperature looks wrong, it decreases",
        ):
            magicc_base._check_tcr_ecs_temp(broken_temp_data)


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
def test_pymagicc_writing_compatibility(
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
    initial_results = package.run().df

    ttweak_factor = 0.9

    mdata = MAGICCData()
    mdata.read(join(package.run_dir, test_filename))
    mdata.df.value *= ttweak_factor
    mdata.write(join(package.run_dir, test_filename), package.version)

    tweaked_results = package.run().df

    for output_to_check in outputs_to_check:
        result = tweaked_results[
            (tweaked_results.variable == output_to_check)
            & (tweaked_results.time >= time_check_min)
            & (tweaked_results.time <= time_check_max)
        ].value
        expected = (
            ttweak_factor
            * initial_results[
                (initial_results.variable == output_to_check)
                & (initial_results.time >= time_check_min)
                & (initial_results.time <= time_check_max)
            ].value
        )
        abstol = np.max([result, expected]) * 10 ** -3
        np.testing.assert_allclose(result, expected, rtol=1e-5, atol=abstol)
