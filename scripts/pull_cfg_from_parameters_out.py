from pymagicc.io import pull_cfg_from_parameters_out_file

cfg = pull_cfg_from_parameters_out_file("/Users/zebedeenicholls/Documents/AGCEC/MCastle/magicc/out/PARAMETERS.OUT")
cfg.write("./TEST.OUT", force=True)
