from unittest.mock import MagicMock, patch

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.eiger import DetectorParams, EigerDetector

from artemis.experiment_plans.fast_grid_scan_plan import FGSComposite, get_plan
from artemis.external_interaction.callbacks.fgs.fgs_callback_collection import (
    FGSCallbackCollection,
)
from artemis.parameters.constants import SIM_BEAMLINE
from artemis.parameters.external_parameters import from_file as default_raw_params
from artemis.parameters.plan_specific.fgs_internal_params import FGSInternalParameters
from artemis.system_tests.conftest import fgs_composite  # noqa


def test_callback_collection_init():
    test_parameters = FGSInternalParameters(**default_raw_params())
    callbacks = FGSCallbackCollection.from_params(test_parameters)
    assert (
        callbacks.ispyb_handler.params.experiment_params
        == test_parameters.experiment_params
    )
    assert (
        callbacks.ispyb_handler.params.artemis_params.detector_params
        == test_parameters.artemis_params.detector_params
    )
    assert (
        callbacks.ispyb_handler.params.artemis_params.ispyb_params
        == test_parameters.artemis_params.ispyb_params
    )
    assert (
        callbacks.ispyb_handler.params.artemis_params == test_parameters.artemis_params
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
        num_images_per_trigger=50,
        num_triggers=1,
        use_roi_mode=False,
        run_number=0,
        det_dist_to_beam_converter_path="src/artemis/unit_tests/test_lookup_table.txt",
    )
    eiger = EigerDetector(name="eiger", prefix="BL03S-EA-EIGER-01:")
    eiger.set_detector_parameters(detector_params)

    # Otherwise odin moves too fast to be tested
    eiger.cam.manual_trigger.put("Yes")

    # S03 currently does not have StaleParameters_RBV
    eiger.odin.check_odin_initialised = lambda: (True, "")

    # These also involve things S03 can't do
    eiger.stage = lambda: None
    eiger.unstage = lambda: True

    yield eiger


@pytest.mark.s03
@patch(
    "artemis.external_interaction.ispyb.store_in_ispyb.StoreInIspyb3D.end_deposition"
)
@patch(
    "artemis.external_interaction.ispyb.store_in_ispyb.StoreInIspyb3D.begin_deposition"
)
@patch("artemis.external_interaction.callbacks.fgs.nexus_callback.NexusWriter")
def test_communicator_in_composite_run(
    nexus_writer: MagicMock,
    ispyb_begin_deposition: MagicMock,
    ispyb_end_deposition: MagicMock,
    fgs_composite: FGSComposite,
):
    nexus_writer.side_effect = [MagicMock(), MagicMock()]
    RE = RunEngine({})

    params = FGSInternalParameters(**default_raw_params())
    params.experiment_params.z_steps = 0
    fgs_composite.eiger.set_detector_parameters(params.artemis_params.detector_params)

    params.artemis_params.beamline = SIM_BEAMLINE
    ispyb_begin_deposition.return_value = ([1, 2], None, 4)

    callbacks = FGSCallbackCollection.from_params(params)
    callbacks.zocalo_handler.wait_for_results = MagicMock(
        autospec=True, return_value=([1, 2, 3], [4, 5, 6])
    )
    callbacks.zocalo_handler.zocalo_interactor.run_end = MagicMock()
    callbacks.zocalo_handler.zocalo_interactor.run_start = MagicMock()

    with patch(
        "artemis.experiment_plans.fast_grid_scan_plan.fast_grid_scan_composite",
        fgs_composite,
    ), patch(
        "artemis.experiment_plans.fast_grid_scan_plan.FGSCallbackCollection.from_params",
        lambda _: callbacks,
    ):
        RE(get_plan(params))

    # nexus writing
    callbacks.nexus_handler.nexus_writer_1.create_nexus_file.assert_called_once()  # type: ignore
    callbacks.nexus_handler.nexus_writer_2.create_nexus_file.assert_called_once()  # type: ignore
    # ispyb
    ispyb_begin_deposition.assert_called_once()
    ispyb_end_deposition.assert_called_once()
    # zocalo
    callbacks.zocalo_handler.zocalo_interactor.run_end.assert_called()
    callbacks.zocalo_handler.zocalo_interactor.run_start.assert_called()
    callbacks.zocalo_handler.wait_for_results.assert_called_once()


def test_callback_collection_list():
    test_parameters = FGSInternalParameters(**default_raw_params())
    callbacks = FGSCallbackCollection.from_params(test_parameters)
    callback_list = list(callbacks)
    assert len(callback_list) == 3
    assert callbacks.ispyb_handler in callback_list
    assert callbacks.nexus_handler in callback_list
    assert callbacks.zocalo_handler in callback_list


def test_subscribe_in_plan():
    test_parameters = FGSInternalParameters(**default_raw_params())
    callbacks = FGSCallbackCollection.from_params(test_parameters)
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
