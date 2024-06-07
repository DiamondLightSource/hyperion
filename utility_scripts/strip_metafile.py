#!/usr/bin/env python3
# This script requires python >= 3.10 but we can't warn about this because
# it will fail at compile time before we can execute a version check
import subprocess
import sys
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory

import h5py


def main() -> int:
    filenames = []
    for option in sys.argv[1:]:
        match option:
            case "--help" | "-h":
                command = sys.argv[0]
                print(
                    f"{command} [metafile]"
                    f"\n\tStrip the /flatfield and /mask from an HDF5 meta file to make it much smaller"
                    f"\n\tTHIS WILL MODIFY THE FILE"
                    f"\n{command} -h | --help"
                    f"\n\tThis help"
                )
                return 0
            case arg:
                filenames.append(arg)

    if len(filenames) < 1:
        sys.stderr.write("Input and/or output file name not supplied\n")
        return 1

    inputfile = filenames[0]
    inputpath = Path(inputfile)

    with TemporaryDirectory() as tempdir:
        tmpfile = f"{tempdir}/{inputpath.name}"
        copyfile(inputfile, tmpfile)
        with h5py.File(tmpfile, "r+") as metafile:
            del metafile["flatfield"]
            metafile.create_dataset("flatfield", (4362, 4148), "<f4")
            del metafile["mask"]
            metafile.create_dataset("mask", (4362, 4148), "<i4")

        h5repack(tempdir, tmpfile, inputfile)

    return 0


def h5repack(tempdir, file, inputfile):
    tempfile = f"{tempdir}/repacked.h5"
    run_command(["h5repack", file, tempfile])
    run_command(["gzip", "--best", tempfile])
    copyfile(f"{tempfile}.gz", f"{inputfile}.gz")


def run_command(args):
    completion = subprocess.run(args, capture_output=True, text=True)
    if completion.returncode:
        sys.stderr.write(f"{args[0]} failed with return code {completion.returncode}")
        sys.stderr.write(completion.stderr)
        sys.exit(1)
    return completion


if __name__ == "__main__":
    sys.exit(main())
