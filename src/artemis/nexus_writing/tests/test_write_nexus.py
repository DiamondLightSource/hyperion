from src.artemis.nexus_writing.write_nexus import NexusWriter
from src.artemis.fast_grid_scan_plan import FullParameters
import tempfile
import h5py
import pytest


def test_given_full_params_when_enter_called_then_files_written_as_expected():
    """It's hard to effectively unit test the nexus writing so this is really a system
    test that confirms that we're passing the right sorts of data to nexgen to get a sensible output."""
    test_full_params = FullParameters()
    test_full_params.ispyb_params.wavelength = 1.0
    test_full_params.ispyb_params.flux = 9.0
    test_full_params.ispyb_params.transmission = 0.5

    nexus_writer = NexusWriter(test_full_params)
    nexus_writer.nexus_file = tempfile.NamedTemporaryFile(delete=False)
    nexus_writer.__enter__()

    with h5py.File(nexus_writer.nexus_file, "r") as written_nexus_file:
        sam_x_data = written_nexus_file["/entry/data/sam_x"][:]
        assert len(sam_x_data) == (test_full_params.grid_scan_params.x_steps + 1) * (
            test_full_params.grid_scan_params.y_steps + 1
        )
        assert sam_x_data[1] - sam_x_data[0] == pytest.approx(
            test_full_params.grid_scan_params.x_step_size
        )
        assert written_nexus_file["/entry/instrument/beam/total_flux"][()] == 9.0


def test_given_full_params_and_nexus_file_with_entry_when_exit_called_then_end_time_written_to_file():
    test_full_params = FullParameters()
    nexus_writer = NexusWriter(test_full_params)
    nexus_writer.nexus_file = tempfile.NamedTemporaryFile(delete=False)

    with h5py.File(nexus_writer.nexus_file, "r+") as written_nexus_file:
        written_nexus_file.require_group("entry")

    nexus_writer.__exit__()

    with h5py.File(nexus_writer.nexus_file, "r") as written_nexus_file:
        assert "end_time" in written_nexus_file["entry"]
