from ._version import get_versions
from .core import MAGICC6, MAGICC7  # noqa
from .io import MAGICCData  # noqa
from .scenarios import (  # noqa
    rcp26,
    rcp45,
    rcp60,
    rcp85,
    rcps,
    read_scen_file,
    zero_emissions,
)

__version__ = get_versions()["version"]
del get_versions


def run(scenario, magicc_version=6, **kwargs):
    """
    Run a MAGICC scenario and return output data and (optionally) config parameters.

    As a reminder, putting ``out_parameters=1`` will cause MAGICC to write out its
    parameters into ``out/PARAMETERS.OUT`` and they will then be read into
    ``output.metadata["parameters"]`` where ``output`` is the returned object.

    Parameters
    ----------
    scenario : :obj:`pymagicc.io.MAGICCData`
        Scenario to run

    magicc_version : int
        MAGICC version to use for the run

    **kwargs
        Parameters overwriting default parameters

    Raises
    ------
    ValueError
        If the magicc_version is not available

    Returns
    -------
    output : :obj:`pymagicc.io.MAGICCData`
        Output of the run with the data in the ``df`` attribute and parameters and
        other metadata in the ``metadata attribute``
    """
    if magicc_version == 6:
        magicc_cls = MAGICC6
    elif magicc_version == 7:
        magicc_cls = MAGICC7
    else:
        raise ValueError("MAGICC version {} is not available".format(magicc_version))

    with magicc_cls() as magicc:
        results = magicc.run(scenario=scenario, **kwargs)

    return results
