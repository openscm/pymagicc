"""Module for useful functions that aren't available elsewhere and don't fit with Pymagicc.

When we say "available elsewhere and don't fit with Pymagicc" we mean that they are
not available to be included as a dependency of Pymagicc nor are they really/solely
related to running MAGICC. A good test of what belongs here is anything for which one
thinks, "I need this, I can't find it anywhere else and I would probably use it again
in another project". One day we may move all these utility functions to another
project to make it easier for ourselves and others to re-use them.
"""

from copy import deepcopy
import re
import datetime


# Thank you https://stackoverflow.com/a/15448887/10473080
def _compile_replacement_regexp(rep_dict):
    return re.compile(
        "|".join([re.escape(k) for k in sorted(rep_dict, key=len, reverse=True)]),
        flags=re.DOTALL,
    )


def _multiple_replace(in_str, rep_dict, compiled_regexp):
    out_str = compiled_regexp.sub(lambda x: rep_dict[x.group(0)], in_str)
    return out_str


def apply_string_substitutions(inputs, substitutions, inverse=False):
    """Apply a number of substitutions to a string(s).

    The substitutions are applied effectively all at once. This means that conflicting
    substitutions don't interact. Where substitutions are conflicting, the one which
    is longer takes precedance. This is confusing so we recommend that you look at
    the examples.

    Parameters
    ----------
    inputs: str, list of str
        The string(s) to which we want to apply the substitutions.

    substitutions: dict
        The substitutions we wish to make. The keys are the strings we wish to
        substitute, the values are the strings which we want to appear in the output
        strings.

    inverse : bool
        If True, do the substitutions the other way around i.e. use the keys as the
        strings we want to appear in the output strings and the values as the strings
        we wish to substitute.

    Returns
    -------
    ``type(input)``
        The input

    Examples
    --------
    >>> apply_string_substitutions("Hello JimBob", {"Jim": "Bob"})
    'Hello BobBob'

    >>> apply_string_substitutions("Hello JimBob", {"Jim": "Bob"}, inverse=True)
    'Hello JimJim'

    >>> apply_string_substitutions(["Hello JimBob", "Jim says, 'Hi Bob'"], {"Jim": "Bob"})
    ['Hello BobBob', "Bob says, 'Hi Bob'"]

    >>> apply_string_substitutions(["Hello JimBob", "Jim says, 'Hi Bob'"], {"Jim": "Bob"}, inverse=True)
    ['Hello JimJim', "Jim says, 'Hi Jim'"]

    >>> apply_string_substitutions("Muttons Butter", {"M": "B", "Button": "Zip"})
    'Buttons Butter'
    # Substitutions don't cascade. If they did, Muttons would become Buttons, then the
    # substitutions "Button" --> "Zip" would be applied and we would end up with
    # "Zips Butter".

    >>> apply_string_substitutions("Muttons Butter", {"Mutton": "Gutter", "tt": "zz"})
    'Gutters Buzzer'
    # Longer substitutions take precedent. Hence Mutton becomes Gutter, not Muzzon.
    """
    if inverse:
        substitutions = {v: k for k, v in substitutions.items()}
    compiled_regexp = _compile_replacement_regexp(substitutions)

    inputs_return = deepcopy(inputs)
    if isinstance(inputs_return, str):
        inputs_return = _multiple_replace(inputs_return, substitutions, compiled_regexp)
    else:
        inputs_return = [
            _multiple_replace(v, substitutions, compiled_regexp) for v in inputs_return
        ]

    return inputs_return


def get_date_time_string():
    """
    Return a timestamp with current date and time.
    """
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d %H:%M")
