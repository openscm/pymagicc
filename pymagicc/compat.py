import os

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


def determine_version():
    version = os.environ.get('MAGICC_VERSION', '6')
    if version not in compat:
        raise ValueError('Could not determine the version of MAGICC used: {}'.format(version))
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
