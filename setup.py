"""
pymagicc

Thin Python wrapper around the
reduced complexity climate model MAGICC6 (http://magicc.org/).

Install using

    pip install pymagicc

On Linux and macOS Wine (https://www.winehq.org) needs to be installed (usually
available with your package manager).

Find usage instructions in the
GitHub repository at https://github.com/openclimatedata/pymagicc.
"""
import versioneer

from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand

PACKAGE_NAME = "pymagicc"
DESCRIPTION = "Python wrapper for the simple climate model MAGICC"
KEYWORDS = ["simple climate model MAGICC python"]
AUTHORS = [
    ("Robert Gieseke", "robert.gieseke@pik-potsdam.de"),
    ("Zeb Nicholls", "zebedee.nicholls@climate-energy-college.org"),
    ("Jared Lewis", "jared.lewis@climate-energy-college.org"),
]
URL = "https://github.com/openclimatedata/pymagicc"
PROJECT_URLS = {
    "Bug Reports": "https://github.com/openclimatedata/pymagicc/issues",
    "Documentation": "https://pymagicc.readthedocs.io/en/latest",
    "Source": "https://github.com/openclimatedata/pymagicc",
}
LICENSE = "GNU Affero General Public License v3"
CLASSIFIERS = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)",
    "Operating System :: OS Independent",
    "Programming Language :: Python :: 3.7",
]
REQUIREMENTS_INSTALL = [
    "pandas>=0.24.0",
    "pandas-datapackage-reader",
    "f90nml",
    "PyYAML",
    "openscm>=0.1.0a",
]
REQUIREMENTS_NOTEBOOKS = [
    "notebook",
    "matplotlib",
    "nbval",
    "expectexception",
    "ipywidgets",
    "appmode",
    "seaborn",
    # TODO use pypi version
    "pyam-iamc>=0.2.0",
]
REQUIREMENTS_TESTS = [
    "pytest>=4.0",
    "pytest-cov",
    "codecov",
    "goodtables",
    "goodtables",
]
REQUIREMENTS_DOCS = [
    "sphinx>=1.4",
    "sphinx_rtd_theme",
    "sphinx-autodoc-typehints",
    "pydoc-markdown",
]
REQUIREMENTS_DEPLOY = ["setuptools>=38.6.0", "twine>=1.11.0", "wheel>=0.31.0"]
REQUIREMENTS_DEV = (
    ["black", "flake8"]
    + REQUIREMENTS_NOTEBOOKS
    + REQUIREMENTS_TESTS
    + REQUIREMENTS_DOCS
    + REQUIREMENTS_DEPLOY
)

README = "README.rst"

REQUIREMENTS_EXTRAS = {
    "notebooks": REQUIREMENTS_NOTEBOOKS,
    "docs": REQUIREMENTS_DOCS,
    "tests": REQUIREMENTS_TESTS,
    "deploy": REQUIREMENTS_DEPLOY,
    "dev": REQUIREMENTS_DEV,
}

PACKAGE_DATA = {
    "": ["*.csv"],
    "pymagicc": [
        "MAGICC6/*.txt",
        "MAGICC6/out/.gitkeep",
        "MAGICC6/run/*.CFG",
        "MAGICC6/run/*.exe",
        "MAGICC6/run/*.IN",
        "MAGICC6/run/*.MON",
        "MAGICC6/run/*.prn",
        "MAGICC6/run/*.SCEN",
    ],
}

with open(README, "r", encoding="utf-8") as f:
    README_TEXT = f.read()


class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import pytest

        pytest.main(self.test_args)


cmdclass = versioneer.get_cmdclass()
cmdclass.update({"test": PyTest})

setup(
    name=PACKAGE_NAME,
    version=versioneer.get_version(),
    description=DESCRIPTION,
    long_description=README_TEXT,
    long_description_content_type="text/x-rst",
    author=", ".join([author[0] for author in AUTHORS]),
    author_email=", ".join([author[1] for author in AUTHORS]),
    url=URL,
    project_urls=PROJECT_URLS,
    license=LICENSE,
    keywords=KEYWORDS,
    classifiers=CLASSIFIERS,
    packages=find_packages(exclude=["tests"]),
    package_data=PACKAGE_DATA,
    include_package_data=True,
    install_requires=REQUIREMENTS_INSTALL,
    extras_require=REQUIREMENTS_EXTRAS,
    cmdclass=cmdclass,
)
