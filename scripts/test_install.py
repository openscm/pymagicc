"""Test that all of our modules can be imported

Thanks https://stackoverflow.com/a/25562415/10473080
"""
import importlib
import pkgutil


import pymagicc


def import_submodules(package_name):
    package = importlib.import_module(package_name)

    for loader, name, is_pkg in pkgutil.walk_packages(package.__path__):
        full_name = package.__name__ + "." + name
        importlib.import_module(full_name)
        if is_pkg:
            import_submodules(full_name)


import_submodules("pymagicc")
print(pymagicc.__version__)
