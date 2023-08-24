from unittest.mock import MagicMock

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import numpy as np
import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.eiger import DetectorParams, EigerDetector

from hyperion.experiment_plans.flyscan_xray_centre_plan import (
    FlyScanXRayCentreComposite,
    run_gridscan_and_move,
)
from hyperion.external_interaction.callbacks.xray_centre.callback_collection import (
    XrayCentreCallbackCollection,
)
from hyperion.parameters.constants import SIM_BEAMLINE
from hyperion.parameters.external_parameters import from_file as default_raw_params
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)


def test_callback_collection_init():
    test_parameters = GridscanInternalParameters(**default_raw_params())
    callbacks = XrayCentreCallbackCollection.from_params(test_parameters)
    assert (
        callbacks.ispyb_handler.params.experiment_params
        == test_parameters.experiment_params
    )
    assert (
        callbacks.ispyb_handler.params.hyperion_params.detector_params
        == test_parameters.hyperion_params.detector_params
    )
    assert (
        callbacks.ispyb_handler.params.hyperion_params.ispyb_params
        == test_parameters.hyperion_params.ispyb_params
    )
    assert (
        callbacks.ispyb_handler.params.hyperion_params
        == test_parameters.hyperion_params
    )
    assert callbacks.ispyb_handler.params == test_parameters
    assert callbacks.zocalo_handler.ispyb == callbacks.ispyb_handler
    assert len(list(callbacks)) == 3


@pytest.fixture()
def eiger():
    detector_params: DetectorParams = DetectorParams(
        current_energy_ev=100,
        exposure_time=0.1,
        directory="/tmp",
        prefix="file_name",
        detector_distance=100.0,
        omega_start=0.0,
        omega_increment=0.1,
        num_images=50,
        use_roi_mode=False,
        run_number=0,
        det_dist_to_beam_converter_path="src/hyperion/unit_tests/test_lookup_table.txt",
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


@pytest.mark.skip(
    reason="Needs better S03 or some other workaround for eiger/odin timeout."
)
@pytest.mark.s03
def test_communicator_in_composite_run(
    nexus_writer: MagicMock,
    ispyb_begin_deposition: MagicMock,
    ispyb_end_deposition: MagicMock,
    eiger: EigerDetector,
):
    nexus_writer.side_effect = [MagicMock(), MagicMock()]
    RE = RunEngine({})

    params = GridscanInternalParameters(**default_raw_params())
    params.hyperion_params.beamline = SIM_BEAMLINE
    ispyb_begin_deposition.return_value = ([1, 2], None, 4)

    callbacks = XrayCentreCallbackCollection.from_params(params)
    callbacks.zocalo_handler._wait_for_result = MagicMock()
    callbacks.zocalo_handler._run_end = MagicMock()
    callbacks.zocalo_handler._run_start = MagicMock()
    callbacks.zocalo_handler.xray_centre_motor_position = np.array([1, 2, 3])

    flyscan_xray_centre_composite = FlyScanXRayCentreComposite()
    # this is where it's currently getting stuck:
    # flyscan_xray_centre_composite.fast_grid_scan.is_invalid = lambda: False
    # but this is not a solution
    # Would be better to use flyscan_xray_centre instead but eiger doesn't work well in S03
    RE(run_gridscan_and_move(flyscan_xray_centre_composite, eiger, params, callbacks))

    # nexus writing
    callbacks.nexus_handler.nexus_writer_1.assert_called_once()
    callbacks.nexus_handler.nexus_writer_2.assert_called_once()
    # ispyb
    ispyb_begin_deposition.assert_called_once()
    ispyb_end_deposition.assert_called_once()
    # zocalo
    callbacks.zocalo_handler._run_start.assert_called()
    callbacks.zocalo_handler._run_end.assert_called()
    callbacks.zocalo_handler._wait_for_result.assert_called_once()


def test_callback_collection_list():
    test_parameters = GridscanInternalParameters(**default_raw_params())
    callbacks = XrayCentreCallbackCollection.from_params(test_parameters)
    callback_list = list(callbacks)
    assert len(callback_list) == 3
    assert callbacks.ispyb_handler in callback_list
    assert callbacks.nexus_handler in callback_list
    assert callbacks.zocalo_handler in callback_list


def test_subscribe_in_plan():
    test_parameters = GridscanInternalParameters(**default_raw_params())
    callbacks = XrayCentreCallbackCollection.from_params(test_parameters)
    document_event_mock = MagicMock()
    callbacks.ispyb_handler.start = document_event_mock
    callbacks.ispyb_handler.stop = document_event_mock
    callbacks.zocalo_handler.start = document_event_mock
    callbacks.zocalo_handler.stop = document_event_mock
    callbacks.nexus_handler.start = document_event_mock
    callbacks.nexus_handler.stop = document_event_mock

    RE = RunEngine()

    @bpp.subs_decorator(callbacks.ispyb_handler)
    def outer_plan():
        @bpp.set_run_key_decorator("inner_plan")
        @bpp.run_decorator(md={"subplan_name": "inner_plan"})
        def inner_plan():
            yield from bps.sleep(0)

        yield from inner_plan()

    RE(outer_plan())

    document_event_mock.assert_called()
