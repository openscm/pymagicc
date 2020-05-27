"""
pymagicc

Thin Python wrapper around the
reduced complexity climate model MAGICC6 (http://magicc.org/).

Install using

    pip install pymagicc

On Linux and macOS Wine (https://www.winehq.org) needs to be installed (usually
available with your package manager).

Find usage instructions in the
GitHub repository at https://github.com/openscm/pymagicc.
"""
import versioneer
from setuptools import find_packages, setup
from setuptools.command.test import test as TestCommand

PACKAGE_NAME = "pymagicc"
DESCRIPTION = "Python wrapper for the simple climate model MAGICC"
KEYWORDS = ["simple climate model MAGICC python"]
AUTHORS = [
    ("Robert Gieseke", "robert.gieseke@pik-potsdam.de"),
    ("Zeb Nicholls", "zebedee.nicholls@climate-energy-college.org"),
    ("Jared Lewis", "jared.lewis@climate-energy-college.org"),
]
URL = "https://github.com/openscm/pymagicc"
PROJECT_URLS = {
    "Bug Reports": "https://github.com/openscm/pymagicc/issues",
    "Documentation": "https://pymagicc.readthedocs.io/en/latest",
    "Source": "https://github.com/openscm/pymagicc",
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
    "pandas-datapackage-reader",
    "f90nml",
    "PyYAML",
    "scmdata>=0.5.0",
]
REQUIREMENTS_NOTEBOOKS = [
    "notebook",
    # "matplotlib",  # TODO: try removing and see what happens
    "expectexception",
    "ipywidgets",
    "appmode",
    "seaborn",
    "pyam-iamc>=0.3.0",
]
REQUIREMENTS_TESTS = [
    "nbval",
    "pytest>=4.0,<5",
    "pytest-benchmark",
    "pytest-cov",
    "pytest-mock",
    "codecov",
    "goodtables",
    "scipy",
]
REQUIREMENTS_DOCS = [
    "sphinx>2.1",
    "sphinx_rtd_theme",
    "sphinx-autodoc-typehints",
    "pydoc-markdown",
]
REQUIREMENTS_DEPLOY = ["setuptools>=38.6.0", "twine>=1.11.0", "wheel>=0.31.0"]
REQUIREMENTS_DEV = (
    [
        "bandit",
        "black",
        "black-nb",
        "flake8",
        "isort",
        "nbdime",
        "pydocstyle",
        "pylint",
    ]
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
    README_LINES = ["Pymagicc", "========", ""]
    add_line = False
    for line in f:
        if line.strip() == ".. sec-begin-long-description":
            add_line = True
        elif line.strip() == ".. sec-end-long-description":
            break
        elif add_line:
            README_LINES.append(line)


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
    long_description="\n".join(README_LINES),
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
