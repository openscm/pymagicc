import copy
import re
import warnings
from datetime import datetime
from os import listdir, remove
from os.path import exists, join
from subprocess import CalledProcessError
from unittest.mock import patch

import f90nml
import numpy as np
import pandas as pd
import pytest
from openscm_units import unit_registry

from pymagicc import MAGICC6, MAGICC7, zero_emissions
from pymagicc.core import MAGICCBase, _clean_value, config
from pymagicc.io import MAGICCData, read_cfg_file

from .test_io import MAGICC6_DIR


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


@pytest.mark.parametrize("tonly", (["junk"], ["junk", "junkier"]))
def test_run_no_output(package, tonly):
    error_msg = re.escape("No output found for only={}".format(tonly))
    with pytest.raises(ValueError, match=error_msg):
        package.run(only=tonly)


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
        "Dataframe scenario input. Please combine all your scenarios into one "
        "Dataframe with Pymagicc and Pandas, then feed this single Dataframe into "
        "Pymagicc's run API."
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
def test_check_config_non_strict(package_non_strict, invalid_config):
    f90nml.write(
        invalid_config, join(package_non_strict.run_dir, "MAGCFG_USER.CFG"), force=True
    )

    error_msg = re.escape(
        "You have more than one `FILE_EMISSCEN_X` flag set. Using more than one "
        "emissions scenario is hard to debug and unnecessary with Pymagicc's "
        "Dataframe scenario input. Please combine all your scenarios into one "
        "Dataframe with Pymagicc and Pandas, then feed this single Dataframe into "
        "Pymagicc's run API."
    )
    with pytest.warns(UserWarning, match=error_msg):
        package_non_strict.check_config()


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
def test_check_config_non_strict_no_pymagicc(package_non_strict, invalid_config):
    f90nml.write(
        invalid_config, join(package_non_strict.run_dir, "MAGCFG_USER.CFG"), force=True
    )

    error_msg = re.escape(
        "PYMAGICC is not the only tuning model that will be used by "
        "`MAGCFG_USER.CFG`: your run is likely to fail/do odd things"
    )
    with pytest.warns(UserWarning, match=error_msg):
        package_non_strict.check_config()


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
    scen = MAGICCData(
        join(MAGICC6_DIR, "RCP26.SCEN"),
        columns={"model": [tmodel], "scenario": [tscenario]},
    )

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

    cols = {"model": ["IMAGE"], "scenario": ["RCP26"], "climate_model": ["MAGICC6"]}
    mdata_initial = MAGICCData(starting_scen, columns=cols)

    mdata_initial.write(written_scen, magicc_version=7)

    mdata_written = MAGICCData(written_scen, columns=cols)
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


@pytest.mark.parametrize("strict", (True, False))
def test_overwrite_config(strict):
    magicc = MAGICC7(strict=strict)
    if magicc.executable is None or not exists(magicc.original_dir):
        pytest.skip("MAGICC7 unavailable")

    magicc.create_copy()
    cfgs = magicc.update_config(filename="MAGCFG_USER.CFG")["nml_allcfgs"]
    assert cfgs["file_tuningmodel_1"] == "PYMAGICC"
    assert cfgs["file_tuningmodel_2"] == "USER"
    if strict:
        assert cfgs["file_emisscen_2"] == "NONE"
    else:
        assert "file_emisscen_2" not in cfgs


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
def test_diagnose_ecs_config_setup(mock_set_years, mock_update_config, magicc_base):
    magicc_base._diagnose_ecs_config_setup()
    mock_set_years.assert_called_with(startyear=1750, endyear=4200)
    mock_update_config.assert_called_with(
        FILE_CO2_CONC="ABRUPT2XCO2_CO2_CONC.IN",
        CO2_SWITCHFROMCONC2EMIS_YEAR=30000,
        RF_TOTAL_RUNMODUS="CO2",
        RF_TOTAL_CONSTANTAFTERYR=2000,
    )


@patch.object(MAGICCBase, "update_config")
@patch.object(MAGICCBase, "set_years")
def test_diagnose_tcr_tcre_config_setup(
    mock_set_years, mock_update_config, magicc_base
):
    magicc_base._diagnose_tcr_tcre_config_setup()
    mock_set_years.assert_called_with(startyear=1750, endyear=2020)
    mock_update_config.assert_called_with(
        FILE_CO2_CONC="1PCTCO2_CO2_CONC.IN",
        CO2_SWITCHFROMCONC2EMIS_YEAR=30000,
        RF_TOTAL_RUNMODUS="CO2",
        RF_TOTAL_CONSTANTAFTERYR=3000,
        OUT_INVERSEEMIS=1,
    )


def _get_mock_diagnosis_results_as_magiccdata(
    fake_time, fake_co2_concs, fake_rf, fake_temp, fake_inverse_emms=None
):
    fake_regions = ["World"] * len(fake_time)

    mock_co2_conc = pd.DataFrame(
        {
            "time": fake_time,
            "unit": ["ppm"] * len(fake_time),
            "variable": ["Atmospheric Concentrations|CO2"] * len(fake_time),
            "value": fake_co2_concs,
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

    to_concat = [mock_co2_conc, mock_rf, mock_temp]

    if fake_inverse_emms is not None:
        mock_inverse_emms = pd.DataFrame(
            {
                "time": fake_time,
                "unit": ["GtC/yr"] * len(fake_time),
                "variable": ["Inverse Emissions|CO2|MAGICC Fossil and Industrial"]
                * len(fake_time),
                "value": fake_inverse_emms,
                "region": fake_regions,
                "model": ["N/A"] * len(fake_time),
                "scenario": ["1%/yr_co2"] * len(fake_time),
            }
        )

        to_concat.append(mock_inverse_emms)

    mock_results = MAGICCData(pd.concat(to_concat))

    return mock_results


@pytest.fixture
def valid_ecs_diagnosis_results():
    startyear = 1700
    endyear = 4000
    spin_up_time = 50
    ecs_start_time = startyear + spin_up_time
    ecs_yr = endyear
    fake_PI_conc = 278.0

    fake_time = np.arange(startyear, endyear + 1)
    fake_concs = np.concatenate(
        (
            fake_PI_conc * np.ones(spin_up_time),
            fake_PI_conc * 2 * np.ones(endyear - startyear - spin_up_time + 1),
        )
    )
    fake_rf = 2.0 * np.log(fake_concs / fake_PI_conc)
    fake_temp = np.log(fake_rf + 1.0) + fake_time / fake_time[1400]

    mock_results = _get_mock_diagnosis_results_as_magiccdata(
        fake_time, fake_concs, fake_rf, fake_temp
    )

    yield {
        "mock_results": mock_results,
        "ecs_time": datetime(ecs_yr, 1, 1),
        "ecs_start_time": datetime(ecs_start_time, 1, 1),
    }


@pytest.fixture
def valid_tcr_tcre_diagnosis_results():
    startyear = 1700
    endyear = 1960
    spin_up_time = 50
    tcre_start_yr = startyear + spin_up_time
    tcr_yr = tcre_start_yr + 70

    fake_PI_conc = 278.0

    fake_time = np.arange(startyear, endyear + 1)
    fake_concs = np.concatenate(
        (
            fake_PI_conc * np.ones(spin_up_time),
            fake_PI_conc * 1.01 ** (np.arange(endyear - startyear - spin_up_time + 1)),
        )
    )
    fake_inverse_emms = np.linspace(0, 60, endyear - startyear + 1)
    fake_rf = 2.0 * np.log(fake_concs / fake_PI_conc)
    fake_temp = np.log(fake_rf + 1.0) + fake_time / fake_time[len(fake_time) // 3]

    mock_results = _get_mock_diagnosis_results_as_magiccdata(
        fake_time, fake_concs, fake_rf, fake_temp, fake_inverse_emms=fake_inverse_emms
    )

    yield {
        "mock_results": mock_results,
        "tcr_time": datetime(tcr_yr, 1, 1),
        "tcr_start_time": datetime(tcre_start_yr, 1, 1),
    }


@patch.object(MAGICCBase, "_check_ecs_temp")
@patch.object(MAGICCBase, "_check_ecs_total_RF")
@patch.object(MAGICCBase, "_get_ecs_ecs_start_yr_from_CO2_concs")
def test_get_ecs_from_diagnosis_results(
    mock_get_ecs_ecs_start_yr_from_CO2_concs,
    mock_check_ecs_total_RF,
    mock_check_ecs_temp,
    valid_ecs_diagnosis_results,
    magicc_base,
):
    test_ecs_time = valid_ecs_diagnosis_results["ecs_time"]
    test_ecs_start_time = valid_ecs_diagnosis_results["ecs_start_time"]
    test_results_df = valid_ecs_diagnosis_results["mock_results"]

    mock_get_ecs_ecs_start_yr_from_CO2_concs.return_value = (
        test_ecs_time,
        test_ecs_start_time,
    )

    expected_ecs = (
        test_results_df.filter(variable="Surface Temperature", time=test_ecs_time)
        .timeseries()
        .squeeze()
    ) * unit_registry("K")

    actual_ecs = magicc_base.get_ecs_from_diagnosis_results(test_results_df)
    assert actual_ecs == expected_ecs

    assert mock_get_ecs_ecs_start_yr_from_CO2_concs.call_count == 1
    assert mock_check_ecs_total_RF.call_count == 1
    assert mock_check_ecs_temp.call_count == 1


@patch.object(MAGICCBase, "_check_tcr_tcre_temp")
@patch.object(MAGICCBase, "_check_tcr_tcre_total_RF")
@patch.object(MAGICCBase, "_get_tcr_tcr_start_yr_from_CO2_concs")
def test_get_tcr_tcre_from_diagnosis_results(
    mock_get_tcr_tcr_start_yr_from_CO2_concs,
    mock_check_tcr_tcre_total_RF,
    mock_check_tcr_tcre_temp,
    valid_tcr_tcre_diagnosis_results,
    magicc_base,
):
    test_tcr_time = valid_tcr_tcre_diagnosis_results["tcr_time"]
    test_tcre_start_time = valid_tcr_tcre_diagnosis_results["tcr_start_time"]
    test_results_df = valid_tcr_tcre_diagnosis_results["mock_results"]

    mock_get_tcr_tcr_start_yr_from_CO2_concs.return_value = [
        test_tcr_time,
        test_tcre_start_time,
    ]

    expected_tcr = (
        test_results_df.filter(variable="Surface Temperature", time=test_tcr_time)
        .timeseries()
        .squeeze()
    ) * unit_registry("K")
    expected_tcre_cumulative_co2 = test_results_df.filter(
        variable="Inverse Emissions|CO2|MAGICC Fossil and Industrial",
        year=range(test_tcre_start_time.year, test_tcr_time.year),
    ).values.sum() * unit_registry("GtC")
    expected_tcre = expected_tcr / expected_tcre_cumulative_co2

    (actual_tcr, actual_tcre,) = magicc_base.get_tcr_tcre_from_diagnosis_results(
        test_results_df
    )
    assert actual_tcr == expected_tcr
    assert actual_tcre == expected_tcre

    assert mock_get_tcr_tcr_start_yr_from_CO2_concs.call_count == 1
    assert mock_check_tcr_tcre_total_RF.call_count == 1
    assert mock_check_tcr_tcre_temp.call_count == 1


def _assert_bad_tcr_ecs_tcre_diagnosis_values_caught(
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
        broken_data = base_data.timeseries()
        col_to_adjust = broken_data.columns == time_to_break
        if test_target == "temperature":
            broken_data.iloc[:, col_to_adjust] -= 0.1
        elif test_target == "rf-tcr":
            broken_data.iloc[:, col_to_adjust] -= 0.1
        else:
            broken_data.iloc[:, col_to_adjust] *= 1.01
            broken_data.iloc[:, col_to_adjust] += 0.01
            broken_data.iloc[-1, col_to_adjust] += 0.1
        with pytest.raises(ValueError, match=regexp_to_match):
            method_to_run(MAGICCData(broken_data), *args)


def test_get_ecs_ecs_start_yr_from_CO2_concs(valid_ecs_diagnosis_results, magicc_base):
    test_results_df = valid_ecs_diagnosis_results["mock_results"]
    test_CO2_data = test_results_df.filter(variable="Atmospheric Concentrations|CO2")

    (
        actual_ecs_yr,
        actual_ecs_start_yr,
    ) = magicc_base._get_ecs_ecs_start_yr_from_CO2_concs(test_CO2_data)
    assert actual_ecs_yr == valid_ecs_diagnosis_results["ecs_time"]
    assert actual_ecs_start_yr == valid_ecs_diagnosis_results["ecs_start_time"]

    _assert_bad_tcr_ecs_tcre_diagnosis_values_caught(
        test_CO2_data,
        magicc_base._get_ecs_ecs_start_yr_from_CO2_concs,
        r"The ECS CO2 concs look wrong.*",
    )


def test_get_tcr_tcr_start_yr_from_CO2_concs(
    valid_tcr_tcre_diagnosis_results, magicc_base
):
    test_results_df = valid_tcr_tcre_diagnosis_results["mock_results"]
    test_CO2_data = test_results_df.filter(variable="Atmospheric Concentrations|CO2")

    (
        actual_tcr_yr,
        actual_tcr_start_yr,
    ) = magicc_base._get_tcr_tcr_start_yr_from_CO2_concs(test_CO2_data)
    assert actual_tcr_yr == valid_tcr_tcre_diagnosis_results["tcr_time"]
    assert actual_tcr_start_yr == valid_tcr_tcre_diagnosis_results["tcr_start_time"]

    _assert_bad_tcr_ecs_tcre_diagnosis_values_caught(
        test_CO2_data,
        magicc_base._get_tcr_tcr_start_yr_from_CO2_concs,
        r"The TCR/TCRE CO2 concs look wrong.*",
    )


def test_check_ecs_total_RF(valid_ecs_diagnosis_results, magicc_base):
    test_results_df = valid_ecs_diagnosis_results["mock_results"]
    test_RF_data = test_results_df.filter(variable="Radiative Forcing")
    magicc_base._check_ecs_total_RF(
        test_RF_data, valid_ecs_diagnosis_results["ecs_start_time"],
    )

    _assert_bad_tcr_ecs_tcre_diagnosis_values_caught(
        test_RF_data,
        magicc_base._check_ecs_total_RF,
        r"The ECS total radiative forcing looks wrong.*",
        valid_ecs_diagnosis_results["ecs_start_time"],
    )


def test_check_tcr_tcre_total_RF(valid_tcr_tcre_diagnosis_results, magicc_base):
    test_results_df = valid_tcr_tcre_diagnosis_results["mock_results"]
    test_RF_data = test_results_df.filter(variable="Radiative Forcing")
    magicc_base._check_tcr_tcre_total_RF(
        test_RF_data, valid_tcr_tcre_diagnosis_results["tcr_time"],
    )

    _assert_bad_tcr_ecs_tcre_diagnosis_values_caught(
        test_RF_data,
        magicc_base._check_tcr_tcre_total_RF,
        r"The TCR/TCRE total radiative forcing looks wrong.*",
        valid_tcr_tcre_diagnosis_results["tcr_time"],
        test_target="rf-tcr",
    )


def test_check_ecs_temp(valid_ecs_diagnosis_results, magicc_base):
    test_results_df = valid_ecs_diagnosis_results["mock_results"]
    test_temp_data = test_results_df.filter(variable="Surface Temperature")

    magicc_base._check_ecs_temp(test_temp_data)

    _assert_bad_tcr_ecs_tcre_diagnosis_values_caught(
        test_temp_data,
        magicc_base._check_ecs_temp,
        r"The ECS surface temperature looks wrong, it decreases",
        test_target="temperature",
    )


def test_check_tcr_tcre_temp(valid_tcr_tcre_diagnosis_results, magicc_base):
    test_results_df = valid_tcr_tcre_diagnosis_results["mock_results"]
    test_temp_data = test_results_df.filter(variable="Surface Temperature")

    magicc_base._check_tcr_tcre_temp(test_temp_data)

    _assert_bad_tcr_ecs_tcre_diagnosis_values_caught(
        test_temp_data,
        magicc_base._check_tcr_tcre_temp,
        r"The TCR/TCRE surface temperature looks wrong, it decreases",
        test_target="temperature",
    )


# integration test (i.e. actually runs magicc) hence slow
@pytest.mark.slow
def test_integration_diagnose_tcr_ecs_tcre(package):
    actual_result = package.diagnose_tcr_ecs_tcre()
    assert isinstance(actual_result, dict)
    assert "tcr" in actual_result
    assert "ecs" in actual_result
    assert "tcre" in actual_result
    assert actual_result["tcr"] < actual_result["ecs"]
    if isinstance(package, MAGICC6):
        # MAGICC6 shipped with pymagicc should be stable
        np.testing.assert_allclose(
            actual_result["tcr"].to("K").magnitude, 1.9733976, rtol=1e-5
        )
        np.testing.assert_allclose(
            actual_result["ecs"].to("K").magnitude, 2.98326, rtol=1e-5
        )
        np.testing.assert_allclose(
            actual_result["tcre"].to("K / TtC").magnitude, 2.28698, rtol=1e-5
        )

    if isinstance(package, MAGICC7):
        # see how stable this is, can delete the test later if it's overly restrictive
        np.testing.assert_allclose(
            actual_result["tcr"].to("K").magnitude, 1.982697, rtol=1e-5
        )
        np.testing.assert_allclose(
            actual_result["ecs"].to("K").magnitude, 2.9948422, rtol=1e-5
        )
        np.testing.assert_allclose(
            actual_result["tcre"].to("K / TtC").magnitude, 2.3189736, rtol=1e-5
        )


@patch.object(MAGICCBase, "_diagnose_ecs_config_setup")
@patch.object(MAGICCBase, "run")
@patch.object(MAGICCBase, "get_ecs_from_diagnosis_results")
def test_diagnose_ecs(
    mock_get_ecs_from_results,
    mock_run,
    mock_diagnose_ecs_setup,
    valid_ecs_diagnosis_results,
    magicc_base,
):
    mock_ecs_val = 3.1 * unit_registry("K")
    mock_run_results = valid_ecs_diagnosis_results["mock_results"]

    mock_run.return_value = mock_run_results
    mock_get_ecs_from_results.return_value = mock_ecs_val

    assert magicc_base.diagnose_ecs()["ecs"] == mock_ecs_val
    assert mock_diagnose_ecs_setup.call_count == 1
    mock_run.assert_called_with(
        only=[
            "Atmospheric Concentrations|CO2",
            "Radiative Forcing",
            "Surface Temperature",
        ],
        scenario=None,
    )
    assert mock_get_ecs_from_results.call_count == 1

    assert magicc_base.diagnose_ecs()["ecs"] == mock_ecs_val
    assert mock_diagnose_ecs_setup.call_count == 2
    assert mock_get_ecs_from_results.call_count == 2

    full_results = magicc_base.diagnose_ecs()
    assert isinstance(full_results, dict)


@patch.object(MAGICCBase, "_diagnose_tcr_tcre_config_setup")
@patch.object(MAGICCBase, "run")
@patch.object(MAGICCBase, "get_tcr_tcre_from_diagnosis_results")
def test_diagnose_tcr_tcre(
    mock_get_tcr_tcre_from_results,
    mock_run,
    mock_diagnose_tcr_tcre_setup,
    valid_tcr_tcre_diagnosis_results,
    magicc_base,
):
    mock_tcr_val = 1.8 * unit_registry("K")
    mock_tcre_val = 2.5 * unit_registry("K / GtC")
    mock_run_results = valid_tcr_tcre_diagnosis_results["mock_results"]

    mock_run.return_value = mock_run_results
    mock_get_tcr_tcre_from_results.return_value = [
        mock_tcr_val,
        mock_tcre_val,
    ]

    assert magicc_base.diagnose_tcr_tcre()["tcr"] == mock_tcr_val
    assert mock_diagnose_tcr_tcre_setup.call_count == 1
    mock_run.assert_called_with(
        only=[
            "Atmospheric Concentrations|CO2",
            "INVERSEEMIS",
            "Radiative Forcing",
            "Surface Temperature",
        ],
        scenario=None,
    )
    assert mock_get_tcr_tcre_from_results.call_count == 1

    assert magicc_base.diagnose_tcr_tcre()["tcre"] == mock_tcre_val
    assert mock_diagnose_tcr_tcre_setup.call_count == 2
    assert mock_get_tcr_tcre_from_results.call_count == 2

    full_results = magicc_base.diagnose_tcr_tcre()
    assert isinstance(full_results, dict)


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


def test_read_parameters(package):
    with type(package)() as magicc:
        # parameters don't exist
        with pytest.raises(FileNotFoundError):
            magicc.read_parameters()

        # Don't read config if it doesn't exist
        magicc.set_config(out_parameters=0)
        magicc.run()

        assert magicc.config is None

    with type(package)() as magicc:
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


# TODO: move to integration tests folder
@pytest.mark.parametrize("rf_method", ["OLBL", "IPCCTAR"])
def test_persistant_state_integration(package, rf_method):
    test_ecs = 1.75
    package.update_config(CORE_CLIMATESENSITIVITY=test_ecs)
    if package.version == 7:
        # MAGICC6 doesn't have this flag so we don't need to adjust anything (yes, we
        # run the test twice, small price to pay for clarity and scalability)
        package.update_config(CORE_CO2CH4N2O_RFMETHOD=rf_method)
        if rf_method == "OLBL":
            pytest.xfail(
                "MAGICC7's ECS only follows its definition with IPCCTAR forcing"
            )

    actual_results = package.diagnose_tcr_ecs_tcre()
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
            {
                "file_ch4_conc": "test_filename",
                "out_concentrations": 1,
                "ch4_switchfromconc2emis_year": 2010,
            },
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
        (
            "RCPODS_WMO2006_Emissions_A1.prn",
            {
                "file_mhalo_emis": "test_filename",
                "out_emissions": 1,
                "scen_histadjust_0no1scale2shift": 0,
            },
            ["Emissions|CFC11", "Emissions|CCl4", "Emissions|CH3Cl"],
            1,
            20000,
        ),
        (
            "RCPODS_WMO2006_MixingRatios_A1.prn",
            {
                "file_mhalo_conc": "test_filename",
                "out_concentrations": 1,
                "scen_histadjust_0no1scale2shift": 0,
                "mhalo_switch_conc2emis_yr": 20000,
            },
            [
                "Atmospheric Concentrations|CFC11",
                "Atmospheric Concentrations|CCl4",
                "Atmospheric Concentrations|CH3Cl",
            ],
            1,
            20000,
        ),
        (
            "HISTRCP85_SOLAR_RF.IN",
            {"file_solar_rf": "test_filename", "out_forcing": 1},
            ["Radiative Forcing|Solar"],
            1,
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
    if ("SCEN" in test_filename) and (package.version == 7):
        # special undocumented flags!!!
        relevant_config["fgas_adjstfutremis2past_0no1scale"] = 0
        relevant_config["mhalo_adjstfutremis2past_0no1scale"] = 0

    iter_dict = copy.deepcopy(relevant_config)
    for key, value in iter_dict.items():
        if value == "test_filename":
            relevant_config[key] = test_filename
        # Handle adjustment to `.prn` handling in MAGICC
        if key == "file_mhalo_emis" and package.version == 7:
            relevant_config["mhalo_prnfile_emis"] = relevant_config.pop(key)
            relevant_config["mhalo_take_prnfile"] = 1
        if key == "file_mhalo_conc" and package.version == 7:
            relevant_config["mhalo_prnfile_conc"] = relevant_config.pop(key)
            relevant_config["mhalo_take_prnfile"] = 1

    package.set_config(conflict="ignore", **relevant_config)

    if (package.version == 6) and test_filename.endswith("SCEN7"):
        error_msg = re.compile("MAGICC6 cannot run SCEN7 files")
        with pytest.raises(ValueError, match=error_msg):
            package.run(only=outputs_to_check)
        return

    if ("SRES" in test_filename) and (package.version == 7):
        # MAGICC7 cannot run SRES SCEN files
        with pytest.raises(CalledProcessError):
            package.run(only=outputs_to_check)
        return

    if ".prn" in test_filename and package.version == 7:
        # MAGICC7's prn handling is not working
        with pytest.raises(CalledProcessError):
            package.run(only=outputs_to_check)
        return

    initial_results = package.run(only=outputs_to_check)

    ttweak_factor = 0.9

    mdata = MAGICCData(
        join(package.run_dir, test_filename),
        columns={"model": ["unspecified"], "scenario": ["unspecified"]},
    )
    mdata._data *= ttweak_factor
    mdata.write(join(package.run_dir, test_filename), package.version)

    tweaked_results = package.run(only=outputs_to_check)

    for output_to_check in outputs_to_check:
        result = (
            tweaked_results.filter(
                variable=output_to_check, year=range(time_check_min, time_check_max + 1)
            )
            .timeseries()
            .values
        )
        initial = (
            initial_results.filter(
                variable=output_to_check, year=range(time_check_min, time_check_max + 1)
            )
            .timeseries()
            .values
        )
        expected = ttweak_factor * initial

        abstol = np.max([result, expected]) * 10 ** -3
        np.testing.assert_allclose(result, expected, rtol=1e-5, atol=abstol)


# TODO: move to integration tests folder
@pytest.mark.parametrize(
    "test_filename, relevant_config, outputs_to_check",
    [
        (
            "RCP26.SCEN",
            {
                "file_emisscen": "test_filename",
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

    package.set_config(conflict="ignore", **relevant_config)
    results = package.run(
        out_emissions=1, out_ascii_binary="ASCII"  # ensure units included
    )

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


def test_zero_run(package):
    package.set_zero_config()
    vars_to_check = ["Surface Temperature", "Radiative Forcing"]
    results = package.run(only=vars_to_check, endyear=2500)
    for var in vars_to_check:
        np.testing.assert_allclose(results.filter(variable=var).timeseries().values, 0)


def test_external_forcing_only_run(package):
    time = zero_emissions["time"]

    forcing_external = 2.0 * np.arange(0, len(time)) / len(time)
    forcing_ext = MAGICCData(
        forcing_external,
        index=time,
        columns={
            "scenario": ["idealised"],
            "model": ["unspecified"],
            "climate_model": ["unspecified"],
            "variable": ["Radiative Forcing|Extra"],
            "unit": ["W / m^2"],
            "todo": ["SET"],
            "region": ["World"],
        },
    )
    forcing_ext_filename = "CUSTOM_EXTRA_RF.IN"
    forcing_ext.metadata = {"header": "External radiative forcing file for testing"}
    forcing_ext.write(join(package.run_dir, forcing_ext_filename), package.version)

    results = package.run(
        rf_extra_read=1,
        file_extra_rf=forcing_ext_filename,
        rf_total_runmodus="QEXTRA",
        endyear=max(time).year,
        rf_initialization_method="ZEROSTARTSHIFT",  # this is default but just in case
        rf_total_constantafteryr=5000,
    )

    # MAGICC's weird last year business means that last result is just constant from previous
    # year and is not treated properly
    # TODO: add this in docs
    validation_output = (
        results.filter(variable="Radiative Forcing", region="World")
        .timeseries()
        .values.squeeze()[:-1]
    )
    validation_input = forcing_external[:-1]
    np.testing.assert_allclose(validation_input, validation_output, rtol=1e-5)
    temperature_global = (
        results.filter(variable="Surface Temperature", region="World")
        .timeseries()
        .values.squeeze()
    )
    assert (temperature_global[1:] - temperature_global[:-1] >= 0).all()


def test_co2_emissions_only(package):
    df = zero_emissions.timeseries()

    time = zero_emissions["time"]
    emms_fossil_co2 = np.linspace(0, 30, len(time))
    df.loc[
        (
            df.index.get_level_values("variable")
            == "Emissions|CO2|MAGICC Fossil and Industrial"
        ),
        :,
    ] = emms_fossil_co2

    scen = MAGICCData(df)
    scen.metadata["header"] = "Test CO2 emissions only file"
    results = package.run(
        scen,
        endyear=max(scen["time"]).year,
        rf_total_constantafteryr=5000,
        rf_total_runmodus="CO2",
        co2_switchfromconc2emis_year=min(scen["time"]).year - 1,
        out_emissions=1,
        only=["Surface Temperature", "Emissions|CO2|MAGICC Fossil and Industrial"],
    )

    output_co2 = (
        results.filter(variable="Em*CO2*Fossil*", region="World")
        .timeseries()
        .values.squeeze()
    )
    assert not (output_co2 == 0).all()
    np.testing.assert_allclose(output_co2, emms_fossil_co2, rtol=0.0005)

    temperature_global = (
        results.filter(variable="Surface Temperature", region="World")
        .timeseries()
        .values.squeeze()
    )
    assert (temperature_global[1:] - temperature_global[:-1] >= 0).all()


@pytest.mark.parametrize("emms_co2_level", [0, 5])
def test_co2_emms_other_rf_run(package, emms_co2_level):
    package.set_zero_config()

    df = zero_emissions.timeseries()

    time = zero_emissions["time"]
    emms_fossil_co2 = np.zeros(len(time))
    emms_fossil_co2[20:] = emms_co2_level

    df.loc[
        (
            df.index.get_level_values("variable")
            == "Emissions|CO2|MAGICC Fossil and Industrial"
        ),
        :,
    ] = emms_fossil_co2

    scen = MAGICCData(df)
    scen.metadata["header"] = "Test CO2 emissions with other RF file"

    forcing_external = 2.0 * np.arange(0, len(time)) / len(time)
    forcing_ext = MAGICCData(
        forcing_external,
        index=time,
        columns={
            "scenario": ["idealised"],
            "model": ["unspecified"],
            "climate_model": ["unspecified"],
            "variable": ["Radiative Forcing|Extra"],
            "unit": ["W / m^2"],
            "todo": ["SET"],
            "region": ["World"],
        },
    )
    forcing_ext.metadata = {"header": "External radiative forcing file for testing"}
    forcing_ext_filename = "CUSTOM_EXTRA_RF.IN"
    forcing_ext.write(join(package.run_dir, forcing_ext_filename), package.version)

    # TODO: fix endyear so it takes from scenario input by default
    results = package.run(
        scen,
        endyear=max(time).year,
        rf_extra_read=1,  # fix writing of 'True'
        file_extra_rf=forcing_ext_filename,
        rf_total_runmodus="ALL",
        rf_initialization_method="ZEROSTARTSHIFT",
        rf_total_constantafteryr=5000,
        co2_switchfromconc2emis_year=min(scen["time"]).year,
        out_emissions=1,
        only=["Radiative Forcing", "Emissions|CO2|MAGICC Fossil and Industrial"],
    )

    np.testing.assert_allclose(
        results.filter(variable="Em*CO2*Fossil*", region="World")
        .timeseries()
        .values.squeeze(),
        emms_fossil_co2,
    )
    # CO2 temperature feedbacks mean that you get a CO2 outgassing, hence CO2 forcing. As a
    # result radiative forcing values don't match exactly. Numerical precision adds to this.
    ext_rf_output_vals = (
        results.filter(variable="Radiative Forcing", region="World")
        .timeseries()
        .values.squeeze()
    )
    zero_rows = (forcing_external == 0) & (ext_rf_output_vals == 0)

    greater_equal_rows = ext_rf_output_vals >= forcing_external
    close_rows_denominator = forcing_external
    close_rows_denominator[zero_rows] = 10 ** -10  # avoid divide by zero
    close_rows = (
        np.abs(ext_rf_output_vals - forcing_external) / close_rows_denominator
        <= 10 ** -3
    )
    matching_rows = greater_equal_rows | close_rows
    assert matching_rows.all()


@patch("pymagicc.core.listdir")
def test_get_output_filenames(mock_listdir):
    mock_listdir.return_value = [
        "DAT_SLR_SEMIEMPI_RATE.OUT",
        "DAT_SLR_SEMIEMPI_RATE.BINOUT",
        "TEMP_OCEANLAYERS.BINOUT",
        "TEMP_OCEANLAYERS.OUT",
        "DAT_SLR_AIS_SMB.OUT",
        "EXTRA.OTHER",
        "PARAMETERS.OUT",
    ]

    m = MAGICC6()
    obs = sorted(m._get_output_filenames())
    exp = sorted(
        [
            "DAT_SLR_SEMIEMPI_RATE.BINOUT",
            "DAT_SLR_AIS_SMB.OUT",
            "TEMP_OCEANLAYERS.OUT",
            "EXTRA.OTHER",
        ]
    )
    np.testing.assert_array_equal(obs, exp)


def test_default_config(package):
    package.default_config
    if package.version == 6:
        expected_config = {
            "file_emissionscenario": "RCP26.SCEN",
            "file_tuningmodel": "PYMAGICC",
        }
    else:
        expected_config = {
            "file_emisscen_2": "NONE",
            "file_emisscen_3": "NONE",
            "file_emisscen_4": "NONE",
            "file_emisscen_5": "NONE",
            "file_emisscen_6": "NONE",
            "file_emisscen_7": "NONE",
            "file_emisscen_8": "NONE",
            "file_tuningmodel_1": "PYMAGICC",
            "file_tuningmodel_2": "USER",
            "file_tuningmodel_3": "USER",
            "file_tuningmodel_4": "USER",
            "file_tuningmodel_5": "USER",
            "file_tuningmodel_6": "USER",
            "file_tuningmodel_7": "USER",
            "file_tuningmodel_8": "USER",
            "file_tuningmodel_9": "USER",
            "file_tuningmodel_10": "USER",
        }

    cfg = read_cfg_file(join(package.run_dir, "MAGCFG_USER.CFG"))
    for key, expected in expected_config.items():
        assert cfg["nml_allcfgs"][key] == expected


def test_out_forcing(package):
    # we get a warning about duplicate timeseries as we're reading both the annual
    # and subannual volcanic forcing, we can safely ignore it here
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", ".*duplicate.*")
        run_kwargs = {"out_forcing": True, "out_ascii_binary": "ASCII"}
        if package.version == 7:
            run_kwargs["out_forcing_subannual"] = True

        res = package.run(**run_kwargs)

    # The results should include sub-annual timeseries by default
    idx = res.filter(variable="Radiative Forcing|Volcanic").timeseries().T.index
    assert (idx[1] - idx[0]).days == 30
    # make sure annual series also read sensibly
    exp = 289.2 if package.version == 6 else 288.636
    assert (
        res.filter(variable="*Conc*CO2", year=1876, region="World").values.squeeze()
        == exp
    )


def test_format_config(package):
    inp = {
        "out_temperature": True,
        "out_allowdynamicvars": False,
        "out_keydata1_vars": ["DAT_SURF_TEMP"],
        "out_dynamic_vars": ["DAT_SURF_TEMP"],
        "out_zero_temp_period": [1990, 2000],
    }
    exp = {
        "out_temperature": 1,
        "out_allowdynamicvars": 0,
        "out_keydata1_vars": ["DAT_SURF_TEMP"],
        "out_dynamic_vars": ["DAT_SURF_TEMP"],
        "out_zero_temp_period": [1990, 2000],
    }

    res = package._convert_out_config_flags_to_integers(inp)
    assert exp == res


@pytest.mark.slow
def test_limit_output(package):
    # Check that we can run the model and only output a single variable
    package.set_output_variables(write_binary=True, write_ascii=False)
    if package.version == 6:
        # MAGICC6 doesn't have this capability
        with pytest.raises(CalledProcessError):
            package.run(out_dynamic_vars=["DAT_SURFACE_TEMP"])
        return

    res = package.run(out_dynamic_vars=["DAT_SURFACE_TEMP"])
    assert listdir(package.out_dir) == ["DAT_SURFACE_TEMP.BINOUT"]
    assert res["variable"].unique() == ["Surface Temperature"]


@pytest.mark.slow
def test_stderr_debug(package):
    if package.version == 6:
        # MAGICC6 doesn't have this capability
        with pytest.raises(ValueError):
            res = package.run(debug=True, only=["Surface Temperature"])
        return

    res = package.run(debug=True, only=["Surface Temperature"])

    assert "stderr" in res.metadata
    assert "<DEBUG>" in res.metadata["stderr"]


@pytest.mark.slow
def test_stderr_verbose(package):
    if package.version == 6:
        # MAGICC6 doesn't have this capability
        with pytest.raises(ValueError):
            res = package.run(debug=True, only=["Surface Temperature"])
        return

    res = package.run(debug="verbose", only=["Surface Temperature"])

    assert "stderr" in res.metadata

    assert "<DEBUG>" not in res.metadata["stderr"]
    assert "<INFO>" in res.metadata["stderr"]


@pytest.mark.slow
def test_stderr_accessible_on_failure(package):
    raised = False
    try:
        package.run(invalid_parameter=True, verbose=True)
    except CalledProcessError as e:
        stderr = e.stderr.decode("ascii")
        assert stderr
        raised = True
    finally:
        assert raised


@pytest.mark.slow
@pytest.mark.parametrize(
    "level,raises",
    [("WARNING", True), ("ERROR", True), ("FATAL", True), ("INFO", False)],
)
def test_stderr_warning_raises_warning(mocker, level, raises):

    # Run magicc, but replaces the error message
    def run(*args, **kwargs):
        import subprocess

        r = subprocess.run(*args, **kwargs)
        r.stderr = level.encode("ascii")
        return r

    mock_run = mocker.patch("pymagicc.core.subprocess").run
    mock_run.side_effect = run

    try:
        with MAGICC7() as m:
            if raises:
                with pytest.warns(
                    UserWarning, match=r"magicc logged a {} message*".format(level)
                ):
                    m.run(out_dynamic_vars=["DAT_SURFACE_TEMP"])
            else:
                with pytest.warns(None) as record:
                    m.run(out_dynamic_vars=["DAT_SURFACE_TEMP"])
                assert len(record) == 0
    except FileNotFoundError:
        pytest.skip("MAGICC7 not installed")


@pytest.mark.slow
def test_empty_output(package):
    package.strict = False
    package.set_output_variables()
    res = package.run(out_dynamic_vars=[])

    assert len(res) == 0


@pytest.mark.slow
def test_empty_output_strict(package):
    package.strict = True
    package.set_output_variables()
    with pytest.raises(ValueError, match="No output found. Check configuration"):
        package.run(out_dynamic_vars=[])


@pytest.mark.slow
def test_empty_output_with_params(package):
    package.strict = False
    package.set_output_variables(parameters=True)
    res = package.run(out_dynamic_vars=[])

    assert len(res) == 0
    assert len(res.metadata["parameters"])


@pytest.mark.slow
def test_failure_message(package, capsys):
    package.strict = False
    emisscen_key = "file_emissionscenario" if package.version == 6 else "file_emisscen"
    remove(join(package.run_dir, package.default_config["nml_allcfgs"][emisscen_key]))
    with pytest.raises(CalledProcessError):
        package.run()

    assert "stderr:\n" in capsys.readouterr().out
