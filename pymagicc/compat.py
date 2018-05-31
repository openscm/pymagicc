import os
import f90nml

from .paths import _get_magicc_paths

compat = {
    '6': {
        'emission_scenario_key': 'file_emissionscenario',
        'num_output_headers': 19
    },
    '7': {
        'emission_scenario_key': 'FILE_EMISSCEN',
        'num_output_headers': 21
    }
}

_version_cache = {}


def _determine_version(magicc_dir):
    user_cfg = f90nml.read(os.path.join(magicc_dir, 'MAGCFG_USER.CFG'))

    if 'FILE_EMISSIONSCENARIO' in user_cfg['nml_allcfgs'] and 'FILE_EMISSCEN_2' in user_cfg['nml_allcfgs']:
        raise ValueError('Invalid MAGCFG_USER.CFG. Should not contain both FILE_EMISSIONSCENARIO and FILE_EMISSCEN_2 keys')

    if 'FILE_EMISSIONSCENARIO' in user_cfg['nml_allcfgs']:
        return '6'
    elif 'FILE_EMISSCEN_2' in user_cfg['nml_allcfgs']:
        return '7'
    raise ValueError('Could not determine the version of MAGICC used')


def determine_version():
    """
    Determine the version of the target MAGICC executable

    Uses expected parameters in the MAGCFG_USER.CFG configuration file. The result is cached as it can be expensive to calculate
    """
    magicc_dir, _ = _get_magicc_paths()
    if magicc_dir in _version_cache:
        return _version_cache[magicc_dir]

    # Determine the version from a directory
    version = _determine_version(magicc_dir)

    _version_cache[magicc_dir] = version
    return version


def get_param(key):
    """
    Get a parameter value which is specific to the targetted version of MAGICC
    """
    version = determine_version()
    try:
        return compat[version][key]
    except KeyError:
        raise ValueError('Invalid key ({}) for version {}'.format(key, version))
