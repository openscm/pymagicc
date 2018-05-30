import os

compat = {
    '6': {
        'run_dir': '',
        'out_dir': '',
        'emission_scenario_key': 'file_emissionscenario',
        'num_output_headers': 19,
        'RCP26_scen': 'RCP3PD.SCEN',
        'RCP45_scen': 'RCP45.SCEN',
        'RCP60_scen': 'RCP6.SCEN',
        'RCP85_scen': 'RCP85.SCEN'
    },
    '7': {
        'run_dir': 'run',
        'out_dir': 'out',
        'emission_scenario_key': 'FILE_EMISSCEN',
        'num_output_headers': 21,
        'RCP26_scen': 'RCP26.SCEN',
        'RCP45_scen': 'RCP45.SCEN',
        'RCP60_scen': 'RCP60.SCEN',
        'RCP85_scen': 'RCP85.SCEN'
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
