from pathlib import Path

import h5py

TEST_EXAMPLE_NEXUS_FILE = Path("ins_8_5.nxs")
TEST_DATA_DIRECTORY = Path("tests/test_data")
TEST_FILENAME = "rotation_scan_test_nexus_0.nxs"

h5item = h5py.File | h5py.Dataset | h5py.Group | h5py.Datatype


def get_entries(dataset: h5py.File) -> set:
    e = set()

    def add_layer(s: set, d: h5item):
        if isinstance(d, h5py.Group):
            for k in d:
                s.add(d.name)
                try:
                    add_layer(s, d[k])
                except KeyError:
                    pass  # ignore linked file contents for now...

    add_layer(e, dataset)
    return e


ENTRIES_EXCEPTIONS_TABLE = {
    "/entry/instrument/source": {"/entry/source"},
    "/entry/instrument/detector_z": {"/entry/instrument/detector/detector_z"},
    "/entry/instrument/transformations": {"/entry/instrument/detector/transformations"},
}


def has_equiv_in(item: str, entries: set):
    if item not in ENTRIES_EXCEPTIONS_TABLE:
        return False
    return ENTRIES_EXCEPTIONS_TABLE[item] & entries == {}


def test_hyperion_rotation_nexus_entries_against_gda():
    with (
        h5py.File(
            str(TEST_DATA_DIRECTORY / TEST_EXAMPLE_NEXUS_FILE), "r"
        ) as example_nexus,
        h5py.File(TEST_DATA_DIRECTORY / TEST_FILENAME, "r") as hyperion_nexus,
    ):
        print(hyperion_entries := get_entries(hyperion_nexus))
        print(gda_entries := get_entries(example_nexus))

        for item in gda_entries:
            assert item in hyperion_entries or has_equiv_in(item, hyperion_entries)
