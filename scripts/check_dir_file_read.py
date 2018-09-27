import argparse
import sys
from os import listdir
from os.path import join


from pymagicc.io import read_cfg_file, MAGICCData


def print_summary(cannot_read, ignored, dir_to_check):
    if cannot_read:
        print(
            "Can't read the following files in {}:\n{}".format(
                dir_to_check, "\n".join(cannot_read)
            )
        )
    else:
        print("Can read all files in {}".format(dir_to_check))

    print("\n\nIgnored:\n{}".format("\n".join(ignored)))


def test_can_read_all_files_in_magicc_dir(dir_to_check):
    cannot_read = []
    ignored = []
    for file_to_read in listdir(dir_to_check):
        try:
            if file_to_read.endswith((".exe", ".mod", ".mat", ".m", ".BINOUT")):
                ignored.append(file_to_read)
            elif file_to_read.endswith(".CFG"):
                read_cfg_file(join(dir_to_check, file_to_read))
            elif file_to_read.endswith("PARAMETERS.OUT"):
                read_cfg_file(join(dir_to_check, file_to_read))
            else:
                mdata = MAGICCData()
                mdata.read(dir_to_check, file_to_read)
        except:
            cannot_read.append(file_to_read)

    print_summary(cannot_read, ignored, dir_to_check)


def main():
    parser = argparse.ArgumentParser(
        prog="check-run-dir-file-read",
        description="Check which files in a "
        "directory can be read by "
        "pymagicc's tools",
    )

    parser.add_argument(
        "readdir", help="The folder where the files to read are located"
    )

    args = parser.parse_args()
    test_can_read_all_files_in_magicc_dir(args.readdir)


if __name__ == "__main__":
    main()
