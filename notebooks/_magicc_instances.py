"""
Module to keep track of MAGICC instances on disk
"""
import logging
import multiprocessing
import shutil
import tempfile

import pymagicc

LOGGER = logging.getLogger(__name__)


class _MagiccInstances:
    def __init__(self, existing_instances):
        """
        Initialise a MAGICC instances handler

        Parameters
        ----------
        existing_instances : :obj:`multiprocessing.managers.DictProxy`
            Dictionary which can store new/existing instances across parallel processes
        """
        self.instances = existing_instances

    def __enter__(self):
        return self

    def cleanup(self):
        """
        Remove all MAGICC instances
        """
        # have to use list as can't modify dict whilst iterating
        insts = list(self.instances.keys())

        for magicc_inst in insts:
            LOGGER.info("removing %s", self.instances[magicc_inst].root_dir)
            shutil.rmtree(self.instances[magicc_inst].root_dir)
            self.instances.pop(magicc_inst)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def __iter__(self):
        return self.instances.__iter__()

    def __getitem__(self, item):
        return self.instances[item]

    @staticmethod
    def _get_key():
        return multiprocessing.current_process().name

    @staticmethod
    def _generate_magicc_root(root_dir):
        return tempfile.mkdtemp(prefix="pymagicc-", dir=root_dir)

    def get(self, root_dir=None, init_callback=None, init_callback_kwargs=None):
        """
        Get a MAGICC object which is ready to run (always uses ``strict=False``)

        This caches the magicc instance used to minimise overhead from copying files.
        Each process gets a unique copy of MAGICC to ensure that each process has
        exclusive access to the magicc instance.

        Parameters
        ----------
        root_dir : str
            Root directory in which to create MAGICC instances.

        init_callback : func
            Function to call when making the MAGICC instance. Must have the
            same function signature as ``default_magicc_setup``.

        init_callback_kwargs : dict
            Keyword arguments to pass to :func:`init_callback`

        Returns
        -------
        pymagicc.MAGICC7
            MAGICC7 object with a valid configuration
        """
        magicc_version = 6  # hard-code for now
        key = (magicc_version, self._get_key())
        try:
            return self.instances[key]
        except KeyError:
            kwargs_tqdm = {}
            if root_dir:
                kwargs_tqdm["root_dir"] = self._generate_magicc_root(root_dir)

            magicc = pymagicc.MAGICC6(strict=False, **kwargs_tqdm)

            magicc.create_copy()
            LOGGER.info("Created new magicc instance: %s - %s", key, magicc.root_dir)

            self.instances[key] = magicc
            if init_callback_kwargs is None:
                init_callback_kwargs = {}

            if init_callback is not None:
                init_callback(magicc, **init_callback_kwargs)

            return magicc