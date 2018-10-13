.. include:: ../README.rst
    :start-after: sec-begin-development
    :end-before: sec-end-development

Contributing
************

.. include:: ../README.rst
    :start-after: sec-begin-contributing
    :end-before: sec-end-contributing

Releasing
*********

The ``make black`` and ``make flake8`` tasks should require no changes.

Make sure that all tests and CI are passing.

The Changelog should contain all major changes.

The docs should be updated and the rendered version be committed to the
repository.

A new release needs to be tagged in the format “vMajor.Minor.Patch”.

All changes should be pushed to GitHub with

::

    git push origin master --tags

Then, a new version can be released on PyPI with

::

    make publish-on-pypi

To test, one can run

::

    make test-pypi-install

to install Pymagicc in a temp directory and to print its version number.

To test publishing on PyPI’s testing instance it is possible to use the
``publish-on-test-pypi`` and ``test-testpypi-install`` tasks. Versions
uploaded there should be deleted after testing.

Finally, the new version needs to be turned into a release on
https://github.com/openclimatedata/pymagicc/releases for automatic
archival on `Zenodo <https://doi.org/10.5281/zenodo.1111815>`__.
