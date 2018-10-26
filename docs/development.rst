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

To release a new version of Pymagicc, there are a number of steps which need to be
taken.

Firstly, ensure that all formatting is correct by running ``make black`` and ``make
flake8``. Make any changes which they require/recommend.

Next make sure all the tests are passing. You can run the tests with ``make test``.
Then make sure all the notebooks are passing their tests. The notebook tests can be
run with ``make test-notebooks``.

Having passed all the formatting and tests locally, you should then push the changes
and ensure that all the code passes CI.

Next all the documentation should be checked and updated where necessary. This
includes ensuring that the Changelog contains all major changes.

Then the next version number needs to be chosen. We follow
`Semantic versioning <https://semver.org/>`_, this means that we have versions which
are in the format "vMajor.Minor.Patch". We then increment the:

- 'Major' when we make backwards-incompatible API changes
- 'Minor' when we add functionality in a backwards-compatible way
- 'Patch' when we make backwards-compatible bug fixes

Having performed all these steps, tag the new release with ``git tag vX.Y.Z``. Push
all the changes to GitHub with

::

    git push origin master --tags

Then, a new version can be released on PyPI (see note below about test releases) with
(getting setup instructions can be found `here <https://blog.jetbrains.com/
pycharm/2017/05/how-to-publish-your-package-on-pypi/>`_)

::

    make publish-on-pypi

To test the released version, one can run

::

    make test-pypi-install

to install Pymagicc in a temporary directory and print its version number.

To ensure the latest Pymagicc version can run in the Mybinder notebook click
the "Launch Binder" link in the Readme on GitHub. This build might take a while.

Finally, the new version needs to be turned into a release. This requires visiting
https://github.com/openclimatedata/pymagicc/releases, pressing 'Draft a new release',
choosing the tag you just pushed, filling out the form and pressing 'Publish release'.
Having done these steps, the package will be automatically archived on
`Zenodo <https://doi.org/10.5281/zenodo.1111815>`__.


Test release
~~~~~~~~~~~~

To test publishing on PyPI’s testing instance it is possible to use the
``publish-on-test-pypi`` and ``test-testpypi-install`` tasks. Versions
uploaded there should be deleted after testing.

