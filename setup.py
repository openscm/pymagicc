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

import os
from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand

path = os.path.abspath(os.path.dirname(__file__))


class PyTest(TestCommand):
    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import pytest

        pytest.main(self.test_args)


with open(os.path.join(path, "README.rst"), "r") as f:
    readme = f.read()


cmdclass = versioneer.get_cmdclass()
cmdclass.update({"test": PyTest})

install_requirements = [
    "pandas",
    "pandas-datapackage-reader",
    "f90nml",
    "pyam-iamc",
    "PyYAML",
]

extra_requirements = {"test": ["pytest", "pytest-cov", "codecov", "goodtables"]}

setup(
    name="pymagicc",
    version=versioneer.get_version(),
    description="Python wrapper for the simple climate model MAGICC",
    long_description=readme,
    long_description_content_type="text/x-rst",
    author="Robert Gieseke",
    author_email="robert.gieseke@pik-potsdam.de",
    url="https://github.com/openclimatedata/pymagicc",
    license="GNU Affero General Public License v3",
    keywords=[],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3.5",
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
