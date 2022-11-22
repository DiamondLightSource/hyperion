from unittest.mock import MagicMock

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import pytest
from bluesky.run_engine import RunEngine
from ophyd.sim import SynSignal

from artemis.devices.eiger import EigerDetector
from artemis.devices.fast_grid_scan_composite import FGSComposite
from artemis.external_interaction.exceptions import ISPyBDepositionNotMade
from artemis.external_interaction.fgs_callback_collection import FGSCallbackCollection
from artemis.fast_grid_scan_plan import run_gridscan_and_move
from artemis.parameters import (
    ISPYB_PLAN_NAME,
    SIM_BEAMLINE,
    DetectorParams,
    FullParameters,
)
from artemis.utils import Point3D


def test_callback_collection_init(
    wait_for_result: MagicMock,
    run_end: MagicMock,
    run_start: MagicMock,
):
    callbacks = FGSCallbackCollection.from_params(FullParameters())
    assert callbacks.ispyb_handler.params == FullParameters()
    assert callbacks.zocalo_handler.ispyb == callbacks.ispyb_handler


def test_callback_collection_subscription_order_triggers_ispyb_before_zocalo(
    nexus_writer: MagicMock,
    mock_ispyb_begin_deposition: MagicMock,
    mock_ispyb_end_deposition: MagicMock,
    wait_for_result: MagicMock,
    run_end: MagicMock,
    run_start: MagicMock,
):
    RE = RunEngine({})

    mock_ispyb_begin_deposition.return_value = ([1, 2], None, 4)

    fgs_undulator_gap = SynSignal(name="fgs_undulator_gap")
    fgs_synchrotron_machine_status_synchrotron_mode = SynSignal(
        name="fgs_synchrotron_machine_status_synchrotron_mode"
    )
    fgs_slit_gaps_xgap = SynSignal(name="fgs_slit_gaps_xgap")
    fgs_slit_gaps_ygap = SynSignal(name="fgs_slit_gaps_ygap")
    detector = SynSignal(name="detector")

    callbacks = FGSCallbackCollection.from_params(FullParameters())
    callbacklist_right_order = [
        callbacks.nexus_handler,
        callbacks.ispyb_handler,
        callbacks.zocalo_handler,
    ]
    assert callbacklist_right_order == list(callbacks)

    @bpp.subs_decorator(list(callbacks))
    @bpp.run_decorator()
    def fake_plan():
        yield from bps.create(ISPYB_PLAN_NAME)
        yield from bps.read(fgs_undulator_gap)
        yield from bps.read(fgs_synchrotron_machine_status_synchrotron_mode)
        yield from bps.read(fgs_slit_gaps_xgap)
        yield from bps.read(fgs_slit_gaps_ygap)
        yield from bps.save()
        # we need to read from something here - otherwise it is the end of the run and
        # the event document is not sent in the format we expect.
        yield from bps.read(detector)

    RE(fake_plan())

    callbacks = FGSCallbackCollection.from_params(FullParameters())
    callbacklist_wrong_order = [
        callbacks.nexus_handler,
        callbacks.zocalo_handler,
        callbacks.ispyb_handler,
    ]
    assert callbacklist_wrong_order != list(callbacks)
    assert callbacks.ispyb_handler.ispyb_ids == (None, None, None)

    @bpp.subs_decorator(callbacklist_wrong_order)
    @bpp.run_decorator()
    def fake_plan_wrong_order():
        yield from bps.create(ISPYB_PLAN_NAME)
        yield from bps.read(fgs_undulator_gap)
        yield from bps.read(fgs_synchrotron_machine_status_synchrotron_mode)
        yield from bps.read(fgs_slit_gaps_xgap)
        yield from bps.read(fgs_slit_gaps_ygap)
        yield from bps.save()

    with pytest.raises(ISPyBDepositionNotMade):
        RE(fake_plan_wrong_order())


@pytest.fixture()
def eiger():
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


@pytest.mark.skip(reason="Needs better S03 or some other workaround.")
@pytest.mark.s03
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
    callbacks = FGSCallbackCollection.from_params(params)
    callbacks.zocalo_handler.xray_centre_motor_position = Point3D(1, 2, 3)

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
    RE(run_gridscan_and_move(fast_grid_scan_composite, eiger, params, callbacks))

    # nexus writing
    callbacks.nexus_handler.nxs_writer_1.assert_called_once()
    callbacks.nexus_handler.assert_called_once()
    # ispyb
    ispyb_begin_deposition.assert_called_once()
    ispyb_end_deposition.assert_called_once()
    # zocalo
    run_start.assert_called()
    run_end.assert_called()
    wait_for_result.assert_called_once()
