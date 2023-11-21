from functools import partial
from typing import Callable, Generator, Sequence
from unittest.mock import MagicMock, patch

import pytest
from bluesky.run_engine import RunEngine
from bluesky.utils import Msg
from dodal.beamlines import i03
from dodal.devices.aperturescatterguard import AperturePositions
from dodal.devices.attenuator import Attenuator
from dodal.devices.backlight import Backlight
from dodal.devices.detector_motion import DetectorMotion
from dodal.devices.eiger import EigerDetector
from dodal.devices.fast_grid_scan import FastGridScan
from dodal.devices.flux import Flux
from dodal.devices.s4_slit_gaps import S4SlitGaps
from dodal.devices.smargon import Smargon
from dodal.devices.synchrotron import Synchrotron
from dodal.devices.undulator import Undulator
from dodal.devices.zebra import Zebra
from ophyd.epics_motor import EpicsMotor
from ophyd.sim import make_fake_device
from ophyd.status import Status

from hyperion.experiment_plans.flyscan_xray_centre_plan import (
    FlyScanXRayCentreComposite,
)
from hyperion.experiment_plans.rotation_scan_plan import RotationScanComposite
from hyperion.external_interaction.callbacks.rotation.callback_collection import (
    RotationCallbackCollection,
)
from hyperion.external_interaction.callbacks.xray_centre.callback_collection import (
    XrayCentreCallbackCollection,
)
from hyperion.external_interaction.ispyb.store_in_ispyb import (
    IspybIds,
    Store3DGridscanInIspyb,
)
from hyperion.external_interaction.zocalo.zocalo_interaction import ZocaloInteractor
from hyperion.log import LOGGER
from hyperion.parameters.constants import GRIDSCAN_OUTER_PLAN
from hyperion.parameters.external_parameters import from_file as raw_params_from_file
from hyperion.parameters.internal_parameters import InternalParameters
from hyperion.parameters.plan_specific.grid_scan_with_edge_detect_params import (
    GridScanWithEdgeDetectInternalParameters,
)
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)

from ...system_tests.external_interaction.conftest import TEST_RESULT_LARGE


def mock_set(motor: EpicsMotor, val):
    motor.user_readback.sim_put(val)  # type: ignore
    return Status(done=True, success=True)


def patch_motor(motor):
    return patch.object(motor, "set", partial(mock_set, motor))


@pytest.fixture
def test_fgs_params():
    return GridscanInternalParameters(**raw_params_from_file())


@pytest.fixture
def test_rotation_params():
    return RotationInternalParameters(
        **raw_params_from_file(
            "tests/test_data/parameter_json_files/good_test_rotation_scan_parameters.json"
        )
    )


@pytest.fixture
def test_rotation_params_nomove():
    return RotationInternalParameters(
        **raw_params_from_file(
            "tests/test_data/parameter_json_files/good_test_rotation_scan_parameters_nomove.json"
        )
    )


@pytest.fixture
def eiger(done_status):
    eiger = i03.eiger(fake_with_ophyd_sim=True)
    eiger.stage = MagicMock(return_value=done_status)
    eiger.unstage = MagicMock(return_value=done_status)
    return eiger


@pytest.fixture
def smargon() -> Generator[Smargon, None, None]:
    smargon = i03.smargon(fake_with_ophyd_sim=True)
    smargon.x.user_setpoint._use_limits = False
    smargon.y.user_setpoint._use_limits = False
    smargon.z.user_setpoint._use_limits = False
    smargon.omega.user_setpoint._use_limits = False

    # Initial positions, needed for stub_offsets
    smargon.stub_offsets.center_at_current_position.disp.sim_put(0)
    smargon.x.user_readback.sim_put(0.0)
    smargon.y.user_readback.sim_put(0.0)
    smargon.z.user_readback.sim_put(0.0)

    with patch_motor(smargon.omega), patch_motor(smargon.x), patch_motor(
        smargon.y
    ), patch_motor(smargon.z):
        yield smargon


@pytest.fixture
def zebra():
    return i03.zebra(fake_with_ophyd_sim=True)


@pytest.fixture
def backlight():
    return i03.backlight(fake_with_ophyd_sim=True)


@pytest.fixture
def detector_motion():
    det = i03.detector_motion(fake_with_ophyd_sim=True)
    det.z.user_setpoint._use_limits = False

    with patch_motor(det.z):
        yield det


@pytest.fixture
def undulator():
    return i03.undulator(fake_with_ophyd_sim=True)


@pytest.fixture
def s4_slit_gaps():
    return i03.s4_slit_gaps(fake_with_ophyd_sim=True)


@pytest.fixture
def synchrotron():
    return i03.synchrotron(fake_with_ophyd_sim=True)


@pytest.fixture
def oav():
    return i03.oav(fake_with_ophyd_sim=True)


@pytest.fixture
def flux():
    return i03.flux(fake_with_ophyd_sim=True)


@pytest.fixture
def attenuator():
    with patch(
        "dodal.devices.attenuator.await_value",
        return_value=Status(done=True, success=True),
        autospec=True,
    ):
        yield i03.attenuator(fake_with_ophyd_sim=True)


@pytest.fixture
def aperture_scatterguard():
    return i03.aperture_scatterguard(
        fake_with_ophyd_sim=True,
        aperture_positions=AperturePositions(
            LARGE=(0, 1, 2, 3, 4),
            MEDIUM=(5, 6, 7, 8, 9),
            SMALL=(10, 11, 12, 13, 14),
            ROBOT_LOAD=(15, 16, 17, 18, 19),
        ),
    )


@pytest.fixture
def RE():
    return RunEngine({}, call_returns_result=True)


@pytest.fixture()
def test_config_files():
    return {
        "zoom_params_file": "tests/test_data/test_jCameraManZoomLevels.xml",
        "oav_config_json": "tests/test_data/test_OAVCentring.json",
        "display_config": "tests/test_data/test_display.configuration",
    }


@pytest.fixture
def test_full_grid_scan_params():
    params = raw_params_from_file(
        "tests/test_data/parameter_json_files/good_test_grid_with_edge_detect_parameters.json"
    )
    return GridScanWithEdgeDetectInternalParameters(**params)


@pytest.fixture
def done_status():
    s = Status()
    s.set_finished()
    return s


@pytest.fixture()
def fake_create_devices(
    eiger: EigerDetector,
    smargon: Smargon,
    zebra: Zebra,
    detector_motion: DetectorMotion,
):
    mock_omega_sets = MagicMock(return_value=Status(done=True, success=True))

    mock_arm_disarm = MagicMock(
        side_effect=zebra.pc.arm.armed.set, return_value=Status(done=True, success=True)
    )
    zebra.pc.arm.set = mock_arm_disarm
    smargon.omega.velocity.set = mock_omega_sets
    smargon.omega.set = mock_omega_sets

    devices = {
        "eiger": eiger,
        "smargon": smargon,
        "zebra": zebra,
        "detector_motion": detector_motion,
        "backlight": i03.backlight(fake_with_ophyd_sim=True),
    }
    return devices


@pytest.fixture()
def fake_create_rotation_devices(
    eiger: EigerDetector,
    smargon: Smargon,
    zebra: Zebra,
    detector_motion: DetectorMotion,
    backlight: Backlight,
    attenuator: Attenuator,
    flux: Flux,
    undulator: Undulator,
    synchrotron: Synchrotron,
    s4_slit_gaps: S4SlitGaps,
    done_status,
):
    mock_omega_sets = MagicMock(return_value=Status(done=True, success=True))

    mock_arm_disarm = MagicMock(
        side_effect=zebra.pc.arm.armed.set, return_value=Status(done=True, success=True)
    )
    zebra.pc.arm.set = mock_arm_disarm
    smargon.omega.velocity.set = mock_omega_sets
    smargon.omega.set = mock_omega_sets

    return RotationScanComposite(
        attenuator=attenuator,
        backlight=backlight,
        detector_motion=detector_motion,
        eiger=eiger,
        flux=flux,
        smargon=smargon,
        undulator=undulator,
        synchrotron=synchrotron,
        s4_slit_gaps=s4_slit_gaps,
        zebra=zebra,
    )


@pytest.fixture
def fake_fgs_composite(smargon: Smargon, test_fgs_params: InternalParameters):
    fake_composite = FlyScanXRayCentreComposite(
        aperture_scatterguard=i03.aperture_scatterguard(fake_with_ophyd_sim=True),
        attenuator=i03.attenuator(fake_with_ophyd_sim=True),
        backlight=i03.backlight(fake_with_ophyd_sim=True),
        eiger=i03.eiger(fake_with_ophyd_sim=True),
        fast_grid_scan=i03.fast_grid_scan(fake_with_ophyd_sim=True),
        flux=i03.flux(fake_with_ophyd_sim=True),
        s4_slit_gaps=i03.s4_slit_gaps(fake_with_ophyd_sim=True),
        smargon=smargon,
        undulator=i03.undulator(fake_with_ophyd_sim=True),
        synchrotron=i03.synchrotron(fake_with_ophyd_sim=True),
        xbpm_feedback=i03.xbpm_feedback(fake_with_ophyd_sim=True),
        zebra=i03.zebra(fake_with_ophyd_sim=True),
    )

    fake_composite.eiger.stage = MagicMock(return_value=done_status)

    fake_composite.aperture_scatterguard.aperture.x.user_setpoint._use_limits = False
    fake_composite.aperture_scatterguard.aperture.y.user_setpoint._use_limits = False
    fake_composite.aperture_scatterguard.aperture.z.user_setpoint._use_limits = False
    fake_composite.aperture_scatterguard.scatterguard.x.user_setpoint._use_limits = (
        False
    )
    fake_composite.aperture_scatterguard.scatterguard.y.user_setpoint._use_limits = (
        False
    )

    fake_composite.fast_grid_scan.scan_invalid.sim_put(False)  # type: ignore
    fake_composite.fast_grid_scan.position_counter.sim_put(0)  # type: ignore

    return fake_composite


def modified_interactor_mock(assign_run_end: Callable | None = None):
    mock = MagicMock(spec=ZocaloInteractor)
    mock.wait_for_result.return_value = TEST_RESULT_LARGE
    if assign_run_end:
        mock.run_end = assign_run_end
    return mock


def modified_store_grid_scan_mock(*args, dcids=(0, 0), dcgid=0, **kwargs):
    mock = MagicMock(spec=Store3DGridscanInIspyb)
    mock.begin_deposition.return_value = IspybIds(
        data_collection_ids=dcids, data_collection_group_id=dcgid, grid_ids=(0, 0)
    )
    return mock


@pytest.fixture
def mock_subscriptions(test_fgs_params):
    with patch(
        "hyperion.external_interaction.callbacks.xray_centre.zocalo_callback.ZocaloInteractor",
        modified_interactor_mock,
    ):
        subscriptions = XrayCentreCallbackCollection.setup()
        start_doc = {
            "subplan_name": GRIDSCAN_OUTER_PLAN,
            "hyperion_internal_parameters": test_fgs_params.json(),
        }
        subscriptions.ispyb_handler.activity_gated_start(start_doc)
        subscriptions.zocalo_handler.activity_gated_start(start_doc)
    subscriptions.ispyb_handler.ispyb = MagicMock(spec=Store3DGridscanInIspyb)
    subscriptions.ispyb_handler.ispyb.begin_deposition = lambda: IspybIds(
        data_collection_ids=(0, 0), data_collection_group_id=0, grid_ids=(0, 0)
    )

    return subscriptions


@pytest.fixture
def mock_rotation_subscriptions(test_rotation_params):
    with patch(
        "hyperion.external_interaction.callbacks.rotation.callback_collection.RotationNexusFileCallback",
        autospec=True,
    ), patch(
        "hyperion.external_interaction.callbacks.rotation.callback_collection.RotationISPyBCallback",
        autospec=True,
    ), patch(
        "hyperion.external_interaction.callbacks.rotation.callback_collection.RotationZocaloCallback",
        autospec=True,
    ):
        subscriptions = RotationCallbackCollection.setup()
    return subscriptions


def fake_read(obj, initial_positions, _):
    initial_positions[obj] = 0
    yield Msg("null", obj)


@pytest.fixture
def simple_beamline(detector_motion, oav, smargon, synchrotron):
    magic_mock = MagicMock()
    magic_mock.oav = oav
    magic_mock.smargon = smargon
    magic_mock.detector_motion = detector_motion
    scan = make_fake_device(FastGridScan)("prefix", name="fake_fgs")
    magic_mock.fast_grid_scan = scan
    magic_mock.synchrotron = synchrotron
    oav.zoom_controller.frst.set("7.5x")
    return magic_mock


class MessageHandler:
    def __init__(self, p: Callable[[Msg], bool], r: Callable[[Msg], object]):
        self.predicate = p
        self.runnable = r


class RunEngineSimulator:
    """This class simulates a Bluesky RunEngine by recording and injecting responses to messages according to the
    bluesky Message Protocol (see bluesky docs for details).
    Basic usage consists of
    1) Registering various handlers to respond to anticipated messages in the experiment plan and fire any
    needed callbacks.
    2) Calling simulate_plan()
    3) Examining the returned message list and making asserts against them"""

    message_handlers = []
    callbacks = {}
    next_callback_token = 0

    def add_handler_for_callback_subscribes(self):
        """Add a handler that registers all the callbacks from subscribe messages so we can call them later.
        You probably want to call this as one of the first things unless you have a good reason not to.
        """
        self.message_handlers.append(
            MessageHandler(
                lambda msg: msg.command == "subscribe",
                lambda msg: self._add_callback(msg.args),
            )
        )

    def add_handler(
        self, commands: Sequence[str], obj_name: str, handler: Callable[[Msg], object]
    ):
        """Add the specified handler for a particular message
        Args:
            commands: the command name for the message as defined in bluesky Message Protocol, or a sequence if more
            than one matches
            obj_name: the name property of the obj to match, can be None as not all messages have a name
            handler: a lambda that accepts a Msg and returns an object; the object is sent to the current yield statement
            in the generator, and is used when reading values from devices, the structure of the object depends on device
            hinting.
        """
        if isinstance(commands, str):
            commands = [commands]

        self.message_handlers.append(
            MessageHandler(
                lambda msg: msg.command in commands
                and (obj_name is None or (msg.obj and msg.obj.name == obj_name)),
                handler,
            )
        )

    def add_wait_handler(self, handler: Callable[[Msg], None], group: str = "any"):
        """Add a wait handler for a particular message
        Args:
            handler: a lambda that accepts a Msg, use this to execute any code that simulates something that's
            supposed to complete when a group finishes
            group: name of the group to wait for, default is any which matches them all
        """
        self.message_handlers.append(
            MessageHandler(
                lambda msg: msg.command == "wait"
                and (group == "any" or msg.kwargs["group"] == group),
                handler,
            )
        )

    def fire_callback(self, document_name, document):
        """Fire all the callbacks registered for this document type in order to simulate something happening
        Args:
             document_name: document name as defined in the Bluesky Message Protocol 'subscribe' call,
             all subscribers filtering on this document name will be called
             document: the document to send
        """
        for callback_func, callback_docname in self.callbacks.values():
            if callback_docname == "all" or callback_docname == document_name:
                callback_func(document_name, document)

    def simulate_plan(self, gen: Generator[Msg, object, object]) -> list[Msg]:
        """Simulate the RunEngine executing the plan
        Args:
            gen: the generator function that executes the plan
        Returns:
            a list of the messages generated by the plan
        """
        messages = []
        send_value = None
        try:
            while msg := gen.send(send_value):
                send_value = None
                messages.append(msg)
                LOGGER.debug(f"<{msg}")
                if handler := next(
                    (h for h in self.message_handlers if h.predicate(msg)), None
                ):
                    send_value = handler.runnable(msg)

                if send_value:
                    LOGGER.debug(f">send {send_value}")
        except StopIteration:
            pass
        return messages

    def _add_callback(self, msg_args):
        self.callbacks[self.next_callback_token] = msg_args
        self.next_callback_token += 1


def add_simple_pin_tip_centre_handlers(sim: RunEngineSimulator):
    """Handlers to simulate a basic fake pin tip"""
    sim.add_handler(
        ("trigger", "read"),
        "oav_mxsc_pin_tip",
        lambda msg: {"oav_mxsc_pin_tip_triggered_tip": {"value": (100, 100)}},
    )
    sim.add_handler(
        "read",
        "oav_mxsc_top",
        lambda msg: {"values": {"value": [50, 51, 52, 53, 54, 55]}},
    )
    sim.add_handler(
        "read",
        "oav_mxsc_bottom",
        lambda msg: {"values": {"value": [50, 49, 48, 47, 46, 45]}},
    )


def add_simple_oav_mxsc_callback_handlers(sim: RunEngineSimulator):
    """Handlers to simulate a basic oav callback firing"""
    sim.add_handler(
        "set",
        "oav_mxsc_enable_callbacks",
        # XXX what are reasonable values for these?
        lambda msg: sim.fire_callback(
            "event",
            {
                "data": {
                    "oav_snapshot_last_saved_path": "/tmp/image1.png",
                    "oav_snapshot_last_path_outer": "/tmp/image2.png",
                    "oav_snapshot_last_path_full_overlay": "/tmp/image3.png",
                    "oav_snapshot_top_left_x": 0,
                    "oav_snapshot_top_left_y": 0,
                    "oav_snapshot_box_width": 100,
                    "smargon_omega": 1,
                    "smargon_x": 0,
                    "smargon_y": 0,
                    "smargon_z": 0,
                    "oav_snapshot_num_boxes_x": 10,
                    "oav_snapshot_num_boxes_y": 10,
                }
            },
        ),
    )


def assert_message_and_return_remaining(messages: list, predicate):
    """Find the next message matching the predicate, assert that we found it
    Return: all the remaining messages starting from the matched message"""
    indices = [i for i in range(len(messages)) if predicate(messages[i])]
    assert indices, f"Nothing matched predicate {predicate}"
    return messages[indices[0] :]
