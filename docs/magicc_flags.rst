.. _`MAGICC flags`:

MAGICC flags
============

This section describes some of the (magical) flags contained in
MAGICC and the gotchas which we have discovered so far. If you have an issue, please
raise it in the `issue tracker <https://github.com/openscm/pymagicc/issues>`_
and we will do our best to assist you before documenting the solution here.

Before moving on, note that Fortran is a case-insensitive language. Thus you shouldn't
worry if you see a flag written as ``MAGICC_FLAG``, ``magicc_flag`` or ``MagICC_FlAg``.
In Pymagicc, the ``f90nml`` package takes care of this case-insensitivity for us.


Conventions
-----------

MAGICC's flags have a few repeating conventions which can make them easier to
understand. However, sometimes the naming convention conflicts with the behaviour so
it's worth double checking if in doubt. Here we summarise a few key conventions:

- endings like ``0NO1SCALE2SHIFT``: in general, if these flags are set to ``0`` then they will do nothing, if set to ``1`` they will adjust the 'input' series to 'target' series by scaling (i.e. multiplying the whole series by a constant) and if set to ``2`` they will adjust the input series to the target series by shifting (i.e. adding/subtracting a constant to the whole series).
- ``ABC_NAMES``: defines the variable names which belong to the group which will commonly be referred to with a prefix of ``ABC`` e.g. ``FGAS_NAMES``: defines the F-gases in MAGICC.
- ``ABC_SWITCHFROMCONC2EMIS_YEAR``: the year in which to switch from being concentration driven to emissions driven for the gas/group of gases ``ABC`` e.g. ``CO2_SWITCHFROMCONC2EMIS_YEAR`` defines the year in which to switch from being |CO2| concentration driven to |CO2| emissions driven.


Undocumented flags
------------------

In the MAGICC6 binary shipped with Pymagicc, all flags are contained in
``MAGCFG_DEFAULTALL_69.CFG``. Hence they are in some sense 'documented' and at least it
is obvious where to look in order to see what all the possible options are.

In MAGICC7, this isn't always the case. Hence, here we provide a list of flags which
are not in ``MAGCFG_DEFAULTALL.CFG`` but are nonetheless valid and useable.

- ``FGAS_ADJSTFUTREMIS2PAST_0NO1SCALE``: adjust future F-gas emissions to past emissions.
- ``MHALO_ADJSTFUTREMIS2PAST_0NO1SCALE``: adjust future Montreal Protocol halogen emissions to past emissions.


Configuration flags
-------------------

When you run MAGICC, you have a series of ``.CFG`` files which set parameter values.
The first two are always (and must be) ``MAGCFG_DEFAULTALL.CFG`` and
``MAGCFG_USER.CFG``. *Exception:* in the compiled binary that is shipped with
Pymagicc, the file it looks for is ``MAGCFG_DEFAULTALL_69.CFG``, not
``MAGCFG_DEFAULTALL.CFG``.

After these two compulsory files, you can then specify extra ``.CFG`` files. Each of
these ``.CFG`` files is specified in ``FILE_TUNINGMODEL_X`` flags.

*Gotcha:* say you have ``FILE_TUNINGMODEL_X=ABCD``, MAGICC will look for
``MAGTUNE_ABCD.CFG``. Note that MAGICC will not look for ``ABCD`` or ``ABCD.CFG``.
Hence if we have ``FILE_TUNINGMODEL_8=PYMAGICC``, then the 8th tuning file MAGICC will
look for will be ``MAGTUNE_PYMAGICC.CFG``. This is why we write the configuration to
``MAGTUNE_PYMAGICC.CFG`` but have ``FILE_TUNINGMODEL_X=PYMAGICC``.

*Gotcha:* if ``FILE_TUNINGMODEL_X`` is set to ``USER``, MAGICC won't look for any
configuration file at all and will simply just move to the next ``FILE_TUNINGMODEL_X``
flag. I think the rationale here is that you have to read ``MAGCFG_USER.CFG`` (see
above) and hence using this flag as a "don't read" flag is safe. Fortunately if you
set ``FILE_TUNINGMODEL_X`` to an empty string i.e. "" then MAGICC will also skip that
``.CFG`` file so there is a safer and more obvious option.

*Gotcha:* the first flag MAGICC6 looks at is ``FILE_TUNING_MODEL``, without any number, whilst the rest are all of the form ``FILE_TUNINGMODEL_X`` where X is a positive integer (i.e. not zero).

*Gotcha:* the convention above changes in MAGICC7, where ``FILE_TUNINGMODEL`` is replaced by ``FILE_TUNINGMODEL_1``.

*Gotcha:* the maximum value of ``X`` in ``FILE_TUNINGMODEL_X`` varies depending on
your binary and there's no way to query the binary except for just trying higher and
higher ``X`` until it fails.

*Gotcha:* each ``.CFG`` file contains a set of parameters, each of which overwrites
any previously read parameter values. i.e. the file pointed to by
``FILE_TUNINGMODEL_4`` overwrites flags set by ``FILE_TUNINGMODEL_3`` etc. However,
each ``.CFG`` file can contain ``FILE_TUNINGMODEL_X`` flags itself. Hence you could
have the following situation:

- ``MAGCFG_DEFAULTALL.CFG`` sets ``FILE_TUNINGMODEL=USER`` and ``FILE_TUNINGMODEL_X=USER`` for all ``X`` i.e. no overwrites on top of what will be read from ``MAGCFG_DEFAULTALL.CFG`` and ``MAGCFG_USER.CFG``
- ``MAGCFG_USER.CFG`` sets e.g. ``FILE_TUNINGMODEL=ZNEXAMPLE`` and ``FILE_TUNINGMODEL_2=PYMAGICC``, leaving everything else untouched
    - hence at this point we would expect MAGICC to read in ``MAGCFG_DEFAULTALL.CFG``, then overwrite its values with values in ``MAGCFG_USER.CFG``, then overwrite those values with values in ``MAGTUNE_ZNEXAMPLE.CFG``, finally overwriting those values with the values in ``MAGTUNE_PYMAGICC.CFG``
- ``MAGTUNE_ZNEXAMPLE.CFG`` sets ``FILE_TUNINGMODEL_2=USER``
    - now ``MAGTUNE_PYMAGICC.CFG`` won't be read at all, destroying our previous impression

An even more confusing situation is this one:

- ``MAGCFG_DEFAULTALL.CFG``` sets ``FILE_TUNINGMODEL=USER`` and ``FILE_TUNINGMODEL_X=USER`` for all X i.e. no overwrites on top of what will be read from ``MAGCFG_DEFAULTALL.CFG`` and ``MAGCFG_USER.CFG``
- ``MAGCFG_USER.CFG`` sets e.g. ``FILE_TUNINGMODEL=ZNEXAMPLE``, ``FILE_TUNINGMODEL_2=RGEX`` and ``FILE_TUNINGMODEL_3=PYMAGICC``, leaving everything else untouched
    - hence at this point we would expect MAGICC to read in ``MAGCFG_DEFAULTALL.CFG``, then overwrite its values with values in ``MAGCFG_USER.CFG``, then overwrite those values with values in ``MAGTUNE_ZNEXAMPLE.CFG```, then overwrite those values with values in ``MAGTUNE_RGEX.CFG``, finally overwriting those values with the values in ``MAGTUNE_PYMAGICC.CFG``
- ``MAGTUNE_ZNEXAMPLE.CFG`` contains no ``FILE_TUNINGMODEL_X`` flags i.e. doesn't change things from our previous expecations
- ``MAGTUNE_RGEX.CFG`` sets ``FILE_TUNINGMODEL=USER`` and ``FILE_TUNINGMODEL_2=USER``.
    - Intuitively, we would expect this to mean that ``MAGTUNE_ZNEXAMPLE.CFG`` and ``MAGTUNE_RGEX.CFG`` will no longer be read, but actually what will happen is that nothing will change. This is because, when ``MAGTUNE_RGEX.CFG`` is read in, it is read in after MAGICC has already looked at the value of the ``FILE_TUNINGMODEL`` and ``FILE_TUNINGMODEL_2`` flags and hence altering this flag, at the point in time when ``MAGTUNE_RGEX.CFG`` is read in, won't have any futher effect.

Finally one more example:

- ``MAGCFG_DEFAULTALL.CFG``` sets ``FILE_TUNINGMODEL=USER`` and ``FILE_TUNINGMODEL_X=USER`` for all X i.e. no overwrites on top of what will be read from ``MAGCFG_DEFAULTALL.CFG`` and ``MAGCFG_USER.CFG``
- ``MAGCFG_USER.CFG`` sets e.g. ``FILE_TUNINGMODEL=ZNEXAMPLE``, ``FILE_TUNINGMODEL_2=RGEX`` and ``FILE_TUNINGMODEL_3=PYMAGICC``, leaving everything else untouched
    - hence at this point we would expect MAGICC to read in ``MAGCFG_DEFAULTALL.CFG``, then overwrite its values with values in ``MAGCFG_USER.CFG``, then overwrite those values with values in ``MAGTUNE_ZNEXAMPLE.CFG```, then overwrite those values with values in ``MAGTUNE_RGEX.CFG``, finally overwriting those values with the values in ``MAGTUNE_PYMAGICC.CFG``
- ``MAGTUNE_ZNEXAMPLE.CFG`` contains ``FILE_TUNINGMODEL_X=""`` for all ``X``
    - this means that MAGICC will skip reading any more tuning files and hence ``MAGTUNE_RGEX.CFG`` will not be read

The reason this is confusing/annoying is that you have to read, and carefully trace,
the hierarchy of every single ``.CFG`` file in order to work out what is going to
happen. The easier option is to run MAGICC and then just see what comes through in
``run/PARAMETERS.OUT``. To help this, there are two small functions in ``pymagicc.io``,
namely ``pull_cfg_from_parameters_out_file`` and ``pull_cfg_from_parameters_out``.

An outline of a function which could do this a priori (i.e. by reading the ``.CFG``
files) might look something like this:

.. code:: python

    from os.path import join, isfile

    import f90nml

    def get_magicc_search_file(base):
        return "MAGTUNE_{}.CFG".format(base)

    def valid_search_model(base):
        return ((base != "") and (base != "USER"))

    def update_cfg_from_tuningmodel_like_magicc(cfg, tuningmodel):
        if valid_search_model(tuningmodel):
            cfg.update(f90nml.read(join(
                run_dir,
                get_magicc_search_file(tuningmodel)
            )))

        return cfg

    def derive_final_cfg(run_dir, namelist_to_derive):
        try:
            cfg = f90nml.read(join(run_dir, "MAGCFG_DEFAULTALL.CFG"))
        except FileNotFoundError:
            cfg = f90nml.read(join(run_dir, "MAGCFG_DEFAULTALL_69.CFG"))

        cfg.update(f90nml.read(join(run_dir, "MAGCFG_USER.CFG")))

        # f90nml reads lowercase by default
        if "file_tuningmodel" in cfg[namelist_to_derive]:
            cfg = update_cfg_from_tuningmodel_like_magicc(
                cfg,
                cfg[namelist_to_derive]["file_tuningmodel"]
            )
        elif "file_tuningmodel_1" in cfg:
            cfg = update_cfg_from_tuningmodel_like_magicc(
                cfg,
                cfg[namelist_to_derive]["file_tuningmodel_1"]
            )

        for i in range(2, 50):
            key_to_check = "file_tuningmodel_{}".format(i)
            if key in cfg[namelist_to_derive]:
                cfg = update_cfg_from_tuningmodel_like_magicc(
                    cfg,
                    cfg[namelist_to_derive][key]
                )

        return cfg

    # Example usage
    run_dir = "/here/there/MAGICC/run"
    namelist_to_derive = "all_cfgs"
    output_file = "./somewhere/else/example.cfg"
    derive_final_cfg(run_dir, namelist_to_derive).write(output_file)


To avoid any really unexpected, silent surprises, we want the pymagicc ``.CFG`` file,
``MAGTUNE_PYMAGICC.CFG`` to overwrite everything else. To save trying to debug
extremely tricky overwriting setups, we enforce simple configurations in Pymagicc and
raise ``ValueError`` if they are not adhered to.


Clash with scenario flags
~~~~~~~~~~~~~~~~~~~~~~~~~

These 'conventions' become more confusing when we compare to what happens with the
emission scenario files.

In MAGICC6 it's simple, there's only one emissions scenario file and it goes in
``FILE_EMISSIONSCENARIO=DFGH``. MAGICC then looks for files that match ``DFGH`` and
``DFGH.SCEN``.

In MAGICC7, there are now multiple ``FILE_EMISSCEN_X`` flags (note the shift from
``FILE_EMISSIONSCENARIO``). The values found in the file specified in each
``FILE_EMISSCEN_X`` flag overwrite any previously read in values.

*Gotcha:* The first emissions scenario file is specified by ``FILE_EMISSCEN`` (without
the number), which matches the MAGICC6 convention for ``FILE_TUNINGMODEL`` but
contradicts the MAGICC7 convention for ``FILE_TUNINGMODEL``.

*Gotcha:* Say we have ``FILE_EMISSCEN=DFGH``, MAGICC7 looks for files that match
``DFGH``, then ``DFGH.SCEN7`` and then ``DFGH.SCEN`` (in that order). Hence the first
emissions scenario can be SCEN7, or SCEN, with preference being given to SCEN7 files
if there are two scenario files with the same stem (i.e. ``RCP26.SCEN7`` is chosen
before ``RCP26.SCEN`` if ``FILE_EMISSCEN=RCP26``).

*Gotcha:* In MAGICC7, only the first ``FILE_EMISSCEN`` can be a ``SCEN`` file (in
MAGICC6 there can only be ``SCEN`` files so this isn't an issue). All other
``FILE_EMISSCEN_X`` files can only be SCEN7 files. The rationale here (I think) is
that SCEN files don't contain easy to read metadata hence overwriting with them is
difficult/dangerous.

*Gotcha:* If the scenario file has a region mode other than World, all World region data are ignored.
This means that all emissions cannot be *currently* stored in a single SCEN7 file as MHalo data is only
provided as a single World region, while most other species are disaggregated by region.

*Gotcha:* If you set ``FILE_EMISSCEN_X=NONE`` then MAGICC will just move on to the
next ``FILE_EMISSCEN_X`` flag. However, from above it's clear that if you set
``FILE_TUNINGMODEL_X=NONE``, MAGICC will look for ``MAGTUNE_NONE.CFG``, not find it
and blow up. Hence there's a direct contradiction there too.

*Gotcha:* Of course the final part is that each ``.CFG`` file can overwrite the
``FILE_EMISSCEN_X`` flags of previous ``.CFG`` hence working out which scenario will actually be run is also not trivial.
