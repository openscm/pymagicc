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
AUTHOR = "Zebedee Nicholls, Robert Gieseke"
EMAIL = "zebedee.nicholls@climate-energy-college.org, robert.gieseke@pik-potsdam.de"
URL = "https://github.com/openclimatedata/pymagicc"

DESCRIPTION = "Python wrapper for the simple climate model MAGICC"
README = "README.rst"

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

install_requirements = [
    "pandas>=0.24.0",
    "pandas-datapackage-reader",
    "f90nml",
    "pyam-iamc @ git+https://github.com/IAMconsortium/pyam.git@master",
    "PyYAML",
    "expectexception",
    "ipywidgets",
    "appmode",
    "openscm @ git+https://github.com/openclimatedata/openscm.git@scmcallib",
    "seaborn",
]

extra_requirements = {
    "tests": [
        "pytest>=4.0",
        "pytest-cov",
        "codecov",
        "goodtables",
        "notebook",
        "matplotlib",
        "nbval",
        "goodtables",
    ],
    "docs": [
        "sphinx>=1.4",
        "sphinx_rtd_theme",
        "sphinx-autodoc-typehints",
        "pydoc-markdown",
    ],
    "deploy": ["setuptools>=38.6.0", "twine>=1.11.0", "wheel>=0.31.0"],
    "dev": ["flake8", "black"],
}

setup(
    name=PACKAGE_NAME,
    version=versioneer.get_version(),
    description=DESCRIPTION,
    long_description=README_TEXT,
    long_description_content_type="text/x-rst",
    author=AUTHOR,
    author_email=EMAIL,
    url=URL,
    license="GNU Affero General Public License v3",
    keywords=[],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
    packages=find_packages(exclude=["tests"]),
    package_data={
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
    },
    include_package_data=True,
    install_requires=install_requirements,
    extras_require=extra_requirements,
    cmdclass=cmdclass,
)
