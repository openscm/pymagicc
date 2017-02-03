from setuptools import setup

setup(
    name='pymagicc',
    version='0.0.1',
    description='Thin Python wrapper for the simple '
                'climate model  MAGICC',
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.4'
        'Programming Language :: Python :: 3.5'
        'Programming Language :: Python :: 3.6'
    ],
    keywords='',
    url='https://github.com/openclimatedata/pymagicc',
    license='AGPL',
    package_data={
        'pymagicc': ['MAGICC6']
    },
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'pandas',
        'f90nml',
        'pytest'
    ]
)
