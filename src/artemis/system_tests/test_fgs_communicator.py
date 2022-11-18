from unittest.mock import MagicMock, patch

import pytest
from bluesky.run_engine import RunEngine

from artemis.devices.eiger import EigerDetector
from artemis.devices.fast_grid_scan_composite import FGSComposite
from artemis.fast_grid_scan_plan import run_gridscan_and_move
from artemis.fgs_communicator import FGSCommunicator
from artemis.parameters import SIM_BEAMLINE, DetectorParams, FullParameters
from artemis.utils import Point3D


@pytest.fixture()
def eiger() -> EigerDetector:
    detector_params: DetectorParams = DetectorParams(
        current_energy=100,
        exposure_time=0.1,
        directory="/tmp",
        prefix="file_name",
        detector_distance=100.0,
        omega_start=0.0,
        omega_increment=0.1,
        num_images=50,
        use_roi_mode=False,
        run_number=0,
        det_dist_to_beam_converter_path="src/artemis/devices/unit_tests/test_lookup_table.txt",
    )
    eiger = EigerDetector(
        detector_params=detector_params, name="eiger", prefix="BL03S-EA-EIGER-01:"
    )

    # Otherwise odin moves too fast to be tested
    eiger.cam.manual_trigger.put("Yes")

    # S03 currently does not have StaleParameters_RBV
    eiger.wait_for_stale_parameters = lambda: None
    eiger.odin.check_odin_initialised = lambda: (True, "")

    yield eiger


@pytest.mark.skip(reason="Needs better S03 eiger/odin or some other workaround.")
@pytest.mark.s03
@patch("artemis.fgs_communicator.StoreInIspyb3D.end_deposition")
@patch("artemis.fgs_communicator.StoreInIspyb3D.begin_deposition")
@patch("artemis.fgs_communicator.NexusWriter")
@patch("artemis.fgs_communicator.wait_for_result")
@patch("artemis.fgs_communicator.run_end")
@patch("artemis.fgs_communicator.run_start")
def test_communicator_in_composite_run(
    run_start: MagicMock,
    run_end: MagicMock,
    wait_for_result: MagicMock,
    nexus_writer: MagicMock,
    ispyb_begin_deposition: MagicMock,
    ispyb_end_deposition: MagicMock,
    eiger: EigerDetector,
):
    nexus_writer.side_effect = [MagicMock(), MagicMock()]
    RE = RunEngine({})

    params = FullParameters()
    params.beamline = SIM_BEAMLINE
    ispyb_begin_deposition.return_value = ([1, 2], None, 4)
    communicator = FGSCommunicator(params)
    communicator.xray_centre_motor_position = Point3D(1, 2, 3)

    fast_grid_scan_composite = FGSComposite(
        insertion_prefix=params.insertion_prefix,
        name="fgs",
        prefix=params.beamline,
    )
    # this is where it's currently getting stuck:
    # fast_grid_scan_composite.fast_grid_scan.is_invalid = lambda: False
    # but this is not a solution
    fast_grid_scan_composite.wait_for_connection()
    # Would be better to use get_plan instead but eiger doesn't work well in S03
    RE(run_gridscan_and_move(fast_grid_scan_composite, eiger, params, communicator))

    # nexus writing
    communicator.nxs_writer_1.assert_called_once()
    communicator.nxs_writer_2.assert_called_once()
    # ispyb
    ispyb_begin_deposition.assert_called_once()
    ispyb_end_deposition.assert_called_once()
    # zocalo
    run_start.assert_called()
    run_end.assert_called()
    wait_for_result.assert_called_once()
