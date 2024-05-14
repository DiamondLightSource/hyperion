from pathlib import Path

import h5py
import pytest
from numpy import dtype

TEST_EXAMPLE_NEXUS_FILE = Path("ins_8_5.nxs")
TEST_DATA_DIRECTORY = Path("tests/test_data")
TEST_FILENAME = "rotation_scan_test_nexus_0.nxs"

h5item = h5py.File | h5py.Dataset | h5py.Group | h5py.Datatype


def get_groups(dataset: h5py.File) -> set:
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


def has_equiv_in(item: str, groups: set, exception_table: dict[str, set[str]]):
    if item not in exception_table.keys():
        return False
    # one of the items in exception_table[item] must be in the tested groups
    return exception_table[item] & groups != set()


def test_has_equiv_in():
    test_table = {"a": {"b", "c"}}
    assert not has_equiv_in("a", {"x", "y", "z"}, test_table)
    assert has_equiv_in("a", {"x", "y", "c"}, test_table)


FilesAndgroups = tuple[h5py.File, set[str], h5py.File, set[str]]


@pytest.fixture
def files_and_groups():
    with (
        h5py.File(
            str(TEST_DATA_DIRECTORY / TEST_EXAMPLE_NEXUS_FILE), "r"
        ) as example_nexus,
        h5py.File(TEST_DATA_DIRECTORY / TEST_FILENAME, "r") as hyperion_nexus,
    ):
        yield (
            example_nexus,
            get_groups(example_nexus),
            hyperion_nexus,
            get_groups(hyperion_nexus),
        )


groups_EXCEPTIONS_TABLE = {
    "/entry/instrument/source": {"/entry/source"},
    "/entry/instrument/detector_z": {"/entry/instrument/detector/detector_z"},
    "/entry/instrument/transformations": {"/entry/instrument/detector/transformations"},
}


def test_hyperion_rotation_nexus_groups_against_gda(
    files_and_groups: FilesAndgroups,
):
    _, gda_groups, _, hyperion_groups = files_and_groups
    for item in gda_groups:
        assert item in hyperion_groups or has_equiv_in(
            item, hyperion_groups, groups_EXCEPTIONS_TABLE
        )


DATATYPE_EXCEPTION_TABLE = {
    "/entry/instrument/detector/detectorSpecific/nimages": (
        dtype("int64"),
        dtype("int32"),
    ),
    "/entry/instrument/detector/detectorSpecific/x_pixels": (
        dtype("uint32"),
        "gda_item_not_present",
    ),
    "/entry/instrument/detector/detectorSpecific/x_pixels_in_detector": (
        dtype("uint32"),
        dtype("int32"),
    ),
    "/entry/instrument/detector/detectorSpecific/y_pixels": (
        dtype("uint32"),
        "gda_item_not_present",
    ),
    "/entry/instrument/detector/detectorSpecific/y_pixels_in_detector": (
        dtype("uint32"),
        dtype("int32"),
    ),
    "/entry/data/data": (dtype("uint32"), dtype("int32")),
    "/entry/instrument/detector/depends_on": (dtype("S48"), dtype("S1024")),
    "/entry/instrument/detector/description": (dtype("S9"), dtype("S1024")),
    "/entry/instrument/detector/distance": (dtype("<f8"), "gda_item_not_present"),
    "/entry/instrument/detector/saturation_value": (
        dtype("int64"),
        "gda_item_not_present",
    ),
    "/entry/instrument/detector/sensor_material": (dtype("S2"), dtype("S1024")),
    "/entry/instrument/detector/type": (dtype("S5"), dtype("S1024")),
    "/entry/instrument/detector/underload_value": (
        dtype("int64"),
        "gda_item_not_present",
    ),
    "/entry/end_time_estimated": (dtype("S10"), "gda_item_not_present"),
    "/entry/start_time": (dtype("S10"), dtype("S20")),
    "/entry/instrument/detector/module/data_origin": (dtype("uint32"), dtype("int32")),
    "/entry/instrument/detector/module/data_size": (dtype("uint32"), dtype("int32")),
    "/entry/instrument/detector/module/data_stride": (dtype("uint32"), dtype("int32")),
    "/entry/instrument/name": (dtype("S20"), dtype("S1024")),
    "/entry/sample/sample_omega/omega_end": (dtype("<f8"), "gda_item_not_present"),
    "/entry/sample/sample_omega/omega_increment_set": (
        dtype("<f8"),
        "gda_item_not_present",
    ),
    "/entry/sample/depends_on": (dtype("S33"), dtype("S1024")),
}


def test_determine_datatype_differences(
    files_and_groups: FilesAndgroups,
):
    gda_nexus, gda_groups, hyperion_nexus, hyperion_groups = files_and_groups
    diffs = {}
    for item in gda_groups:
        # we checked separately if all expected items should be there
        # but we should probably still check the excepted ones here??
        if item in hyperion_groups:
            hyperion_group = hyperion_nexus[item]
            gda_group = gda_nexus[item]
            print(hyperion_group, gda_group)
            for dset_or_attr in hyperion_group:
                try:
                    if not isinstance(hyperion_group[dset_or_attr], h5py.Group):
                        hyperion_dtype = "hyperion_item_not_present"
                        gda_dtype = "gda_item_not_present"
                        try:  # ignore external links for now, remove this later
                            hyperion_dtype = hyperion_group[dset_or_attr].dtype
                            gda_dtype = gda_group[dset_or_attr].dtype
                        except Exception as e:
                            print(e)
                        print(
                            item,
                            dset_or_attr,
                            hyperion_dtype,
                            gda_dtype,
                            hyperion_dtype == gda_dtype,
                        )
                        if not hyperion_dtype == gda_dtype:
                            diffs[item + "/" + dset_or_attr] = (
                                hyperion_dtype,
                                gda_dtype,
                            )
                except Exception:
                    ...  # as above

    print(diffs)
