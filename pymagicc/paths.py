import os


def _get_magicc_paths():
    default_executable = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "MAGICC6/MAGICC6_4Download/magicc6.exe"
    )

    executable = os.environ.get('MAGICC_EXECUTABLE', default_executable)
    return os.path.dirname(executable), os.path.basename(executable)
