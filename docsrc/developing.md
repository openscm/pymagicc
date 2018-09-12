# Developing

## Updating the Docs

The [Pydoc documentation](https://openclimatedata.github.io/pymagicc/) uses
[Pydocmd](https://github.com/NiklasRosenstein/pydoc-markdown/) which uses
[MkDocs](https://www.mkdocs.org/).

The setting of pages happens in a Yaml configuration file:
<https://github.com/openclimatedata/pymagicc/blob/master/mkdocs.yml>

API documentation pages are auto-generated. Additional pages can be added
in `docsrc`. Readme and Changelog are re-used through symbolic links into the
same directory.

The docs can be rebuilt with

    make docs

The rendered docs should only be committed to the repository before a new release,
so that they reflect the version available on PyPI.

## Releasing

The `make black` and `make flake8` tasks should require no changes.

Make sure that all tests and CI are passing.

The Changelog should contain all major changes.

The docs should be updated and the rendered version be committed to the repository.

A new release needs to be tagged in the format "vMajor.Minor.Patch".

All changes should be pushed to GitHub with

    git push origin master --tags

Then, a new version can be released on PyPI with

    make publish-on-pypi

To test, one can run

    make test-pypi-install

to install Pymagicc in a temp directory and to print its version number.

To test publishing on PyPI's testing instance it is possible to use the `publish-on-test-pypi` and `test-testpypi-install` tasks. Versions uploaded there should be deleted after testing.

Finally, the new version needs to be turned into a release on <https://github.com/openclimatedata/pymagicc/releases> for automatic archival on [Zenodo](https://doi.org/10.5281/zenodo.1111815).
