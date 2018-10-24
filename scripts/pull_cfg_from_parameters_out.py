from pymagicc.io import pull_cfg_from_parameters_out_file

file_to_read = "/path/to/somewhere/PARAMETERS.OUT"
cfg = pull_cfg_from_parameters_out_file(file_to_read)
cfg.write("./TEST.OUT", force=True)
