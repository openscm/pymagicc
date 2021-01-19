from pymagicc.scenarios import rcps


def test_all_rcps_included():
    assert set(rcps["scenario"]) == {"RCP26", "RCP45", "RCP60", "RCP85"}
