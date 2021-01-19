import os

import pytest


def _get_readme_codeblocks():
    codeblocks = []
    with open("README.rst", "r") as fh:
        in_codeblock = False
        codeblock = []
        for line in fh.readlines():
            line = line.strip(os.linesep)
            if line == ".. code:: python":
                in_codeblock = True

            elif in_codeblock:
                if line and not line.startswith("    "):
                    in_codeblock = False
                    codeblocks.append(os.linesep.join(codeblock))
                    codeblock = []
                else:
                    if not line:
                        codeblock.append(os.linesep)
                    else:
                        codeblock.append(line[4 : ])

    return codeblocks


@pytest.mark.parametrize("codeblock", _get_readme_codeblocks())
def test_readme(codeblock):
    try:
        # https://stackoverflow.com/a/62851176/353337
        exec(codeblock, {"__MODULE__": "__main__"})
    except Exception:
        print("Codeblock failed:\n{}".format(codeblock))
        raise
