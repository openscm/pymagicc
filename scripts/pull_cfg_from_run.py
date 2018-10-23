"""Pull a single config file from a hierarchy of MAGICC ``.CFG`` files

The ``.CFG`` files should all be in the same directory, exactly like a MAGICC ``run``
directory.

This script is untested and should be used with care!! For more explanation, see

TODO: add link to docs and maybe move this to pymagicc.utils.
"""
from os.path import join, abspath, dirname, isfile
from pprint import pprint

import f90nml


NML_TO_DERIVE = 'nml_allcfgs'
HERE = dirname(abspath(__file__))

RUN_DIR = join(HERE, '..', 'pymagicc', 'MAGICC6', 'run')
DEFAULT_CFG = join(RUN_DIR, 'MAGCFG_DEFAULTALL_69.CFG')
USER_CFG = join(RUN_DIR, 'MAGCFG_USER.CFG')

output_cfg_file = join(HERE, "DERIVED_MAGICC_{}.CFG".format(NML_TO_DERIVE.upper()))

def overwrite_namelist_with(base, overwriter, min_tuningmodel_level):
    new = base
    for key in overwriter[NML_TO_DERIVE]:
        new[NML_TO_DERIVE][key] = overwriter[NML_TO_DERIVE][key]

    tuning_files_to_check = [
        'file_tuningmodel_' + str(i)
        for i in range(min_tuningmodel_level, 50)
    ]
    special_first_tuningmodel = 'file_tuningmodel'
    if min_tuningmodel_level <= 1:
        tuning_files_to_check.insert(0, special_first_tuningmodel)

    for key in tuning_files_to_check:
        if key in overwriter[NML_TO_DERIVE]:
            tuning_model = base[NML_TO_DERIVE][key]
            if tuning_model == 'USER':
                continue

            tune_file = join(RUN_DIR, 'MAGTUNE_' + tuning_model + '.CFG')
            cfg_file = join(RUN_DIR, 'MAGCFG_' + tuning_model + '.CFG')

            if isfile(tune_file):
                tunemodel_nml = f90nml.read(tune_file)
            elif isfile(cfg_file):
                tunemodel_nml = f90nml.read(cfg_file)

            min_tuningmodel_level = 2 if key == special_first_tuningmodel else int(key.split("_")[2])

            new = overwrite_namelist_with(new, tunemodel_nml, min_tuningmodel_level)

    return new

cfg_default = f90nml.read(DEFAULT_CFG)
cfg_final = f90nml.Namelist({NML_TO_DERIVE: cfg_default[NML_TO_DERIVE]})

cfg_user = f90nml.read(USER_CFG)
cfg_final = overwrite_namelist_with(cfg_final, cfg_user, min_tuningmodel_level=0)

# clear out tuningmodel keys as we want all config to be in one file
for key in ['file_tuningmodel_' + str(i) for i in range(1,11)]:
    if key in cfg_final[NML_TO_DERIVE]:
        del cfg_final[NML_TO_DERIVE][key]


print('Writing {}'.format(output_cfg_file))
with open(output_cfg_file, 'w') as nml_file:
    cfg_final.write(nml_file)
