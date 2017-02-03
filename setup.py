"""
pymagicc
--------

Thin Python wrapper around the reduced complexity climate model
[MAGICC 6](http://magicc.org/).

**Install** using ::

    pip install pymagicc

Find **usage** instructions in the repository
<https://github.com/openclimatedata/pymagicc>.

"""

from setuptools import setup
from setuptools.command.test import test as TestCommand


class PyTest(TestCommand):

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        import pytest
        pytest.main(self.test_args)

setup(
    name='pymagicc',
    version='0.4',
    description='Thin Python wrapper for the simple climate model  MAGICC',
    long_description=__doc__,
    author='Robert Gieseke',
    author_email='robert.gieseke@pik-potsdam.de',
    url='https://github.com/openclimatedata/pymagicc',
    license='GNU Affero General Public License v3',
    keywords=[],
        classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6'
    ],
    packages=['pymagicc'],
    package_data={'pymagicc': [
        'MAGICC6/*.txt',
        'MAGICC6/MAGICC6_4Download/*.CFG',
        'MAGICC6/MAGICC6_4Download/*.exe',
        'MAGICC6/MAGICC6_4Download/*.IN',
        'MAGICC6/MAGICC6_4Download/*.MON',
        'MAGICC6/MAGICC6_4Download/*.prn',
        'MAGICC6/MAGICC6_4Download/*.SCEN'
    ]},
    include_package_data=True,
    zip_safe=False,
    install_requires=['pandas', 'f90nml'],
    tests_require=['pytest'],
    cmdclass={'test': PyTest}
)
