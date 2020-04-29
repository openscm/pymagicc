import re
import warnings
from unittest.mock import patch

import pytest

from pymagicc.utils import apply_string_substitutions


@patch("pymagicc.utils._compile_replacement_regexp")
@patch("pymagicc.utils._multiple_replace")
@patch("pymagicc.utils._check_unused_substitutions")
@patch("pymagicc.utils._check_duplicate_substitutions")
def test_apply_string_substitutions(
    mock_check_duplicate_substitutions,
    mock_check_unused_substitutions,
    mock_multiple_replace,
    mock_compile_replacement_regexp,
):
    treturn = "mocked return"
    mock_multiple_replace.return_value = treturn

    tcompiled_regexp = "mocked regexp"
    mock_compile_replacement_regexp.return_value = tcompiled_regexp

    tinput = "Hello JimBob"
    tsubstitutions = {"Jim": "Bob"}
    tcase_insensitive = "mocked case insensitivity"
    tunused_substitutions = "mocked unused substitutions"

    result = apply_string_substitutions(
        tinput,
        tsubstitutions,
        case_insensitive=tcase_insensitive,
        unused_substitutions=tunused_substitutions,
    )

    assert result == treturn

    mock_check_duplicate_substitutions.assert_called_with(tsubstitutions)
    mock_check_unused_substitutions.assert_called_with(
        tsubstitutions, tinput, tunused_substitutions, tcase_insensitive
    )
    mock_compile_replacement_regexp.assert_called_with(
        tsubstitutions, case_insensitive=tcase_insensitive
    )
    mock_multiple_replace.assert_called_with(tinput, tsubstitutions, tcompiled_regexp)


# would be ideal to have these come from docstring rather
# than being duplicated
@pytest.mark.parametrize(
    "inputs, substitutions, expected",
    [
        ("Hello JimBob", {"Jim": "Bob"}, "Hello BobBob"),
        (
            ["Hello JimBob", "Jim says, 'Hi Bob'"],
            {"Jim": "Bob"},
            ["Hello BobBob", "Bob says, 'Hi Bob'"],
        ),
        ("Muttons Butter", {"M": "B", "Button": "Zip"}, "Buttons Butter"),
        ("Muttons Butter", {"Mutton": "Gutter", "tt": "zz"}, "Gutters Buzzer"),
    ],
)
def test_apply_string_substitutions_default(inputs, substitutions, expected):
    result = apply_string_substitutions(inputs, substitutions)
    assert result == expected


@pytest.mark.parametrize(
    "inputs, substitutions, expected",
    [
        ("Hello JimBob", {"Jim": "Bob"}, "Hello JimJim"),
        (
            ["Hello JimBob", "Jim says, 'Hi Bob'"],
            {"Jim": "Bob"},
            ["Hello JimJim", "Jim says, 'Hi Jim'"],
        ),
    ],
)
def test_apply_string_substitutions_inverse(inputs, substitutions, expected):
    result = apply_string_substitutions(inputs, substitutions, inverse=True)
    assert result == expected


@pytest.mark.parametrize(
    "inputs, substitutions, expected", [("Butter", {"buTTer": "Gutter"}, "Gutter")]
)
def test_apply_string_substitutions_case_insensitive(inputs, substitutions, expected):
    result = apply_string_substitutions(inputs, substitutions, case_insensitive=True)
    assert result == expected


@pytest.mark.parametrize(
    "inputs, substitutions, unused_substitutions",
    [
        ("Butter", {"teeth": "tooth"}, "ignore"),
        ("Butter", {"teeth": "tooth"}, "warn"),
        ("Butter", {"teeth": "tooth"}, "raise"),
        ("Butter", {"teeth": "tooth"}, "junk"),
    ],
)
def test_apply_string_substitutions_unused_substitutions(
    inputs, substitutions, unused_substitutions
):
    if unused_substitutions == "ignore":
        result = apply_string_substitutions(
            inputs, substitutions, unused_substitutions=unused_substitutions
        )
        assert result == inputs
        return

    msg = "No substitution available for {'" + "{}".format(inputs) + "'}"
    if unused_substitutions == "warn":
        with warnings.catch_warnings(record=True) as warn_result:
            apply_string_substitutions(
                inputs, substitutions, unused_substitutions=unused_substitutions
            )

        assert len(warn_result) == 1
        assert str(warn_result[0].message) == msg
    elif unused_substitutions == "raise":
        with pytest.raises(ValueError, match=re.escape(msg)):
            apply_string_substitutions(
                inputs, substitutions, unused_substitutions=unused_substitutions
            )
    else:
        msg = re.escape("Invalid value for unused_substitutions, please see the docs")
        with pytest.raises(ValueError, match=msg):
            apply_string_substitutions(
                inputs, substitutions, unused_substitutions=unused_substitutions
            )


def test_apply_string_substitutions_duplicate_substitutions():
    # Note: we can ignore non case insensitive substitutions as if you try to generate
    # a dictionary with a duplicate key, it will just be overwritten
    assert {"teeth": "tooth", "teeth": "other"} == {"teeth": "other"}  # noqa


@pytest.mark.parametrize(
    "inputs, substitutions, expected",
    [("teeth", {"teeth": "tooth", "Teeth": "tooth"}, "tooth")],
)
def test_apply_string_substitutions_duplicate_substitutions_case_insensitive(
    inputs, substitutions, expected
):
    res = apply_string_substitutions(inputs, substitutions)
    assert res == expected

    error_msg = re.escape(
        "Duplicate case insensitive substitutions: {}".format(substitutions)
    )
    with pytest.raises(ValueError, match=error_msg):
        apply_string_substitutions(inputs, substitutions, case_insensitive=True)
