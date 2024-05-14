import asyncio
import gzip
import json
import logging
import sys
import threading
from functools import partial
from typing import Any, Callable, Generator, Optional, Sequence
from unittest.mock import AsyncMock, MagicMock, patch

import bluesky.plan_stubs as bps
import pytest
from bluesky.run_engine import RunEngine
from bluesky.utils import Msg
from dodal.beamlines import beamline_utils, i03
from dodal.beamlines.beamline_parameters import (
    GDABeamlineParameters,
)
from dodal.devices.aperturescatterguard import (
    ApertureFiveDimensionalLocation,
    AperturePositions,
    ApertureScatterguard,
    SingleAperturePosition,
)
from dodal.devices.attenuator import Attenuator
from dodal.devices.backlight import Backlight
from dodal.devices.dcm import DCM
from dodal.devices.detector.detector_motion import DetectorMotion
from dodal.devices.eiger import EigerDetector
from dodal.devices.fast_grid_scan import GridScanCompleteStatus
from dodal.devices.flux import Flux
from dodal.devices.oav.oav_detector import OAVConfigParams
from dodal.devices.robot import BartRobot
from dodal.devices.s4_slit_gaps import S4SlitGaps
from dodal.devices.smargon import Smargon
from dodal.devices.synchrotron import Synchrotron, SynchrotronMode
from dodal.devices.undulator import Undulator
from dodal.devices.webcam import Webcam
from dodal.devices.zebra import Zebra
from dodal.log import LOGGER as dodal_logger
from dodal.log import set_up_all_logging_handlers
from ophyd.epics_motor import EpicsMotor
from ophyd.sim import NullStatus
from ophyd.status import DeviceStatus, Status
from ophyd_async.core import set_sim_value
from ophyd_async.core.async_status import AsyncStatus
from ophyd_async.epics.motion.motor import Motor
from scanspec.core import Path as ScanPath
from scanspec.specs import Line

from hyperion.experiment_plans.flyscan_xray_centre_plan import (
    FlyScanXRayCentreComposite,
)
from hyperion.experiment_plans.rotation_scan_plan import RotationScanComposite
from hyperion.external_interaction.callbacks.logging_callback import (
    VerbosePlanExecutionLoggingCallback,
)
from hyperion.log import (
    ALL_LOGGERS,
    ISPYB_LOGGER,
    LOGGER,
    NEXUS_LOGGER,
    _get_logging_dir,
    do_default_logging_setup,
)
from hyperion.parameters.gridscan import GridScanWithEdgeDetect, ThreeDGridScan
from hyperion.parameters.rotation import RotationScan

i03.DAQ_CONFIGURATION_PATH = "tests/test_data/test_daq_configuration"


def raw_params_from_file(filename):
    with open(filename) as f:
        return json.loads(f.read())


def default_raw_params():
    return raw_params_from_file(
        "tests/test_data/new_parameter_json_files/test_gridscan_param_defaults.json"
    )


def create_dummy_scan_spec(x_steps, y_steps, z_steps):
    x_line = Line("sam_x", 0, 10, 10)
    y_line = Line("sam_y", 10, 20, 20)
    z_line = Line("sam_z", 30, 50, 30)

    specs = [y_line * ~x_line, z_line * ~x_line]
    specs = [ScanPath(spec.calculate()) for spec in specs]
    return [spec.consume().midpoints for spec in specs]


def _reset_loggers(loggers):
    """Clear all handlers and tear down the logging hierarchy, leave logger references intact."""
    clear_log_handlers(loggers)
    for logger in loggers:
        if logger.name != "Hyperion":
            # Hyperion parent is configured on module import, do not remove
            logger.parent = logging.getLogger()


def clear_log_handlers(loggers: Sequence[logging.Logger]):
    for logger in loggers:
        for handler in logger.handlers:
            handler.close()
        logger.handlers.clear()


def pytest_runtest_setup(item):
    markers = [m.name for m in item.own_markers]
    if item.config.getoption("logging") and "skip_log_setup" not in markers:
        if LOGGER.handlers == []:
            if dodal_logger.handlers == []:
                print("Initialising Hyperion logger for tests")
                do_default_logging_setup(dev_mode=True)
        if ISPYB_LOGGER.handlers == []:
            print("Initialising ISPyB logger for tests")
            set_up_all_logging_handlers(
                ISPYB_LOGGER,
                _get_logging_dir(),
                "hyperion_ispyb_callback.log",
                True,
                10000,
            )
        if NEXUS_LOGGER.handlers == []:
            print("Initialising nexus logger for tests")
            set_up_all_logging_handlers(
                NEXUS_LOGGER,
                _get_logging_dir(),
                "hyperion_ispyb_callback.log",
                True,
                10000,
            )
    else:
        print("Skipping log setup for log test - deleting existing handlers")
        _reset_loggers([*ALL_LOGGERS, dodal_logger])


def pytest_runtest_teardown(item):
    if "dodal.beamlines.beamline_utils" in sys.modules:
        sys.modules["dodal.beamlines.beamline_utils"].clear_devices()
    markers = [m.name for m in item.own_markers]
    if "skip_log_setup" in markers:
        _reset_loggers([*ALL_LOGGERS, dodal_logger])


@pytest.fixture
def RE():
    RE = RunEngine({}, call_returns_result=True)
    RE.subscribe(
        VerbosePlanExecutionLoggingCallback()
    )  # log all events at INFO for easier debugging
    yield RE
    try:
        RE.halt()
    except Exception as e:
        print(f"Got exception while halting RunEngine {e}")
    finally:
        stopped_event = threading.Event()

        def stop_event_loop():
            RE.loop.stop()  # noqa: F821
            stopped_event.set()

        RE.loop.call_soon_threadsafe(stop_event_loop)
        stopped_event.wait(10)
    del RE


def mock_set(motor: EpicsMotor, val):
    motor.user_setpoint.sim_put(val)  # type: ignore
    motor.user_readback.sim_put(val)  # type: ignore
    return Status(done=True, success=True)


def patch_motor(motor: EpicsMotor):
    return patch.object(motor, "set", MagicMock(side_effect=partial(mock_set, motor)))


async def mock_good_coroutine():
    return asyncio.sleep(0)


def mock_async_motor_move(motor: Motor, val, *args, **kwargs):
    set_sim_value(motor.user_setpoint, val)
    set_sim_value(motor.user_readback, val)
    return mock_good_coroutine()  # type: ignore


def patch_async_motor(motor: Motor, initial_position=0):
    set_sim_value(motor.user_setpoint, initial_position)
    set_sim_value(motor.user_readback, initial_position)
    set_sim_value(motor.deadband, 0.001)
    set_sim_value(motor.motor_done_move, 1)
    return patch.object(
        motor, "_move", AsyncMock(side_effect=partial(mock_async_motor_move, motor))
    )


@pytest.fixture
def beamline_parameters():
    return GDABeamlineParameters.from_file(
        "tests/test_data/test_beamline_parameters.txt"
    )


@pytest.fixture
def test_fgs_params():
    return ThreeDGridScan(
        **raw_params_from_file(
            "tests/test_data/new_parameter_json_files/good_test_parameters.json"
        )
    )


@pytest.fixture
def test_panda_fgs_params(test_fgs_params: ThreeDGridScan):
    test_fgs_params.use_panda = True
    return test_fgs_params


@pytest.fixture
def test_rotation_params():
    return RotationScan(
        **raw_params_from_file(
            "tests/test_data/new_parameter_json_files/good_test_rotation_scan_parameters.json"
        )
    )


@pytest.fixture
def test_rotation_params_nomove():
    return RotationScan(
        **raw_params_from_file(
            "tests/test_data/new_parameter_json_files/good_test_rotation_scan_parameters_nomove.json"
        )
    )


@pytest.fixture
def done_status():
    s = Status()
    s.set_finished()
    return s


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
    smargon.omega.velocity._use_limits = False

    # Initial positions, needed for stub_offsets
    smargon.stub_offsets.center_at_current_position.disp.sim_put(0)  # type: ignore
    smargon.x.user_readback.sim_put(0.0)  # type: ignore
    smargon.y.user_readback.sim_put(0.0)  # type: ignore
    smargon.z.user_readback.sim_put(0.0)  # type: ignore

    with (
        patch_motor(smargon.omega),
        patch_motor(smargon.x),
        patch_motor(smargon.y),
        patch_motor(smargon.z),
        patch_motor(smargon.chi),
        patch_motor(smargon.phi),
    ):
        yield smargon


@pytest.fixture
def zebra():
    RunEngine()
    zebra = i03.zebra(fake_with_ophyd_sim=True)

    def mock_side(*args, **kwargs):
        zebra.pc.arm.armed._backend._set_value(*args, **kwargs)  # type: ignore
        return Status(done=True, success=True)

    zebra.pc.arm.set = MagicMock(side_effect=mock_side)
    return zebra


@pytest.fixture
def backlight():
    return i03.backlight(fake_with_ophyd_sim=True)


@pytest.fixture
def fast_grid_scan():
    return i03.fast_grid_scan(fake_with_ophyd_sim=True)


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
    RunEngine()  # A RE is needed to start the bluesky loop
    synchrotron = i03.synchrotron(fake_with_ophyd_sim=True)
    set_sim_value(synchrotron.synchrotron_mode, SynchrotronMode.USER)
    set_sim_value(synchrotron.topup_start_countdown, 10)
    return synchrotron


@pytest.fixture
def oav(test_config_files):
    parameters = OAVConfigParams(
        test_config_files["zoom_params_file"], test_config_files["display_config"]
    )
    oav = i03.oav(fake_with_ophyd_sim=True, params=parameters)
    oav.snapshot.trigger = MagicMock(return_value=NullStatus())
    return oav


@pytest.fixture
def flux():
    return i03.flux(fake_with_ophyd_sim=True)


@pytest.fixture
def pin_tip():
    return i03.pin_tip_detection(fake_with_ophyd_sim=True)


@pytest.fixture
def ophyd_pin_tip_detection():
    RunEngine()  # A RE is needed to start the bluesky loop
    pin_tip_detection = i03.pin_tip_detection(fake_with_ophyd_sim=True)
    return pin_tip_detection


@pytest.fixture
def robot(done_status):
    RunEngine()  # A RE is needed to start the bluesky loop
    robot = i03.robot(fake_with_ophyd_sim=True)
    set_sim_value(robot.barcode.bare_signal, ["BARCODE"])
    robot.set = MagicMock(return_value=done_status)
    return robot


@pytest.fixture
def attenuator():
    with patch(
        "dodal.devices.attenuator.await_value",
        return_value=Status(done=True, success=True),
        autospec=True,
    ):
        attenuator = i03.attenuator(fake_with_ophyd_sim=True)
        attenuator.actual_transmission.sim_put(0.49118047952)  # type: ignore
        yield attenuator


@pytest.fixture
def xbpm_feedback(done_status):
    xbpm = i03.xbpm_feedback(fake_with_ophyd_sim=True)
    xbpm.trigger = MagicMock(return_value=done_status)  # type: ignore
    yield xbpm
    beamline_utils.clear_devices()


@pytest.fixture
def dcm(RE):
    dcm = i03.dcm(fake_with_ophyd_sim=True)
    set_sim_value(dcm.energy_in_kev.user_readback, 12.7)
    set_sim_value(dcm.pitch_in_mrad.user_readback, 1)
    return dcm


@pytest.fixture
def qbpm1():
    return i03.qbpm1(fake_with_ophyd_sim=True)


@pytest.fixture
def vfm(RE):
    vfm = i03.vfm(fake_with_ophyd_sim=True)
    vfm.bragg_to_lat_lookup_table_path = (
        "tests/test_data/test_beamline_vfm_lat_converter.txt"
    )
    return vfm


@pytest.fixture
def vfm_mirror_voltages():
    voltages = i03.vfm_mirror_voltages(fake_with_ophyd_sim=True)
    voltages.voltage_lookup_table_path = "tests/test_data/test_mirror_focus.json"
    yield voltages
    beamline_utils.clear_devices()


@pytest.fixture
def undulator_dcm(RE, dcm):
    undulator_dcm = i03.undulator_dcm(fake_with_ophyd_sim=True)
    undulator_dcm.dcm = dcm
    undulator_dcm.dcm_roll_converter_lookup_table_path = (
        "tests/test_data/test_beamline_dcm_roll_converter.txt"
    )
    undulator_dcm.dcm_pitch_converter_lookup_table_path = (
        "tests/test_data/test_beamline_dcm_pitch_converter.txt"
    )
    yield undulator_dcm
    beamline_utils.clear_devices()


@pytest.fixture
def webcam(RE) -> Generator[Webcam, Any, Any]:
    webcam = i03.webcam(fake_with_ophyd_sim=True)
    with patch.object(webcam, "_write_image"):
        yield webcam


@pytest.fixture
def aperture_scatterguard(done_status, RE):
    AperturePositions.LARGE = SingleAperturePosition(
        location=ApertureFiveDimensionalLocation(0, 1, 2, 3, 4),
        name="Large",
        GDA_name="LARGE_APERTURE",
        radius_microns=100,
    )
    AperturePositions.MEDIUM = SingleAperturePosition(
        location=ApertureFiveDimensionalLocation(5, 6, 2, 8, 9),
        name="Medium",
        GDA_name="MEDIUM_APERTURE",
        radius_microns=50,
    )
    AperturePositions.SMALL = SingleAperturePosition(
        location=ApertureFiveDimensionalLocation(10, 11, 2, 13, 14),
        name="Small",
        GDA_name="SMALL_APERTURE",
        radius_microns=20,
    )
    AperturePositions.ROBOT_LOAD = SingleAperturePosition(
        location=ApertureFiveDimensionalLocation(15, 16, 2, 18, 19),
        name="Robot_load",
        GDA_name="ROBOT_LOAD",
        radius_microns=None,
    )
    ap_sg = i03.aperture_scatterguard(
        fake_with_ophyd_sim=True,
        aperture_positions=AperturePositions(
            AperturePositions.LARGE,
            AperturePositions.MEDIUM,
            AperturePositions.SMALL,
            AperturePositions.ROBOT_LOAD,
        ),
    )
    with (
        patch_async_motor(ap_sg.aperture.x),
        patch_async_motor(ap_sg.aperture.y),
        patch_async_motor(ap_sg.aperture.z, 2),
        patch_async_motor(ap_sg.scatterguard.x),
        patch_async_motor(ap_sg.scatterguard.y),
    ):
        RE(bps.abs_set(ap_sg, ap_sg.aperture_positions.SMALL))  # type: ignore
        yield ap_sg


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
        "tests/test_data/new_parameter_json_files/good_test_grid_with_edge_detect_parameters.json"
    )
    return GridScanWithEdgeDetect(**params)


@pytest.fixture()
def fake_create_devices(
    eiger: EigerDetector,
    smargon: Smargon,
    zebra: Zebra,
    detector_motion: DetectorMotion,
    aperture_scatterguard: ApertureScatterguard,
):
    mock_omega_sets = MagicMock(return_value=Status(done=True, success=True))

    smargon.omega.velocity.set = mock_omega_sets
    smargon.omega.set = mock_omega_sets

    devices = {
        "eiger": eiger,
        "smargon": smargon,
        "zebra": zebra,
        "detector_motion": detector_motion,
        "backlight": i03.backlight(fake_with_ophyd_sim=True),
        "ap_sg": aperture_scatterguard,
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
    aperture_scatterguard: ApertureScatterguard,
    synchrotron: Synchrotron,
    s4_slit_gaps: S4SlitGaps,
    dcm: DCM,
    robot: BartRobot,
    done_status,
):
    mock_omega_sets = MagicMock(return_value=Status(done=True, success=True))
    mock_omega_velocity_sets = MagicMock(return_value=Status(done=True, success=True))

    smargon.omega.velocity.set = mock_omega_velocity_sets
    smargon.omega.set = mock_omega_sets

    smargon.omega.max_velocity.sim_put(131)  # type: ignore

    return RotationScanComposite(
        attenuator=attenuator,
        backlight=backlight,
        dcm=dcm,
        detector_motion=detector_motion,
        eiger=eiger,
        flux=flux,
        smargon=smargon,
        undulator=undulator,
        aperture_scatterguard=aperture_scatterguard,
        synchrotron=synchrotron,
        s4_slit_gaps=s4_slit_gaps,
        zebra=zebra,
        robot=robot,
    )


@pytest.fixture
def zocalo(done_status):
    zoc = i03.zocalo(fake_with_ophyd_sim=True)
    zoc.stage = MagicMock(return_value=done_status)
    zoc.unstage = MagicMock(return_value=done_status)
    return zoc


def mock_gridscan_kickoff_complete(gridscan):
    gridscan_start = DeviceStatus(device=gridscan)
    gridscan_start.set_finished()
    gridscan_result = GridScanCompleteStatus(device=gridscan)
    gridscan_result.set_finished()
    gridscan.kickoff = MagicMock(return_value=gridscan_start)
    gridscan.complete = MagicMock(return_value=gridscan_result)


@pytest.fixture
def fake_fgs_composite(
    smargon: Smargon,
    test_fgs_params: ThreeDGridScan,
    RE: RunEngine,
    done_status,
    attenuator,
    xbpm_feedback,
    synchrotron,
    aperture_scatterguard,
    zocalo,
    dcm,
):
    fake_composite = FlyScanXRayCentreComposite(
        aperture_scatterguard=aperture_scatterguard,
        attenuator=attenuator,
        backlight=i03.backlight(fake_with_ophyd_sim=True),
        dcm=dcm,
        # We don't use the eiger fixture here because .unstage() is used in some tests
        eiger=i03.eiger(fake_with_ophyd_sim=True),
        fast_grid_scan=i03.fast_grid_scan(fake_with_ophyd_sim=True),
        flux=i03.flux(fake_with_ophyd_sim=True),
        s4_slit_gaps=i03.s4_slit_gaps(fake_with_ophyd_sim=True),
        smargon=smargon,
        undulator=i03.undulator(fake_with_ophyd_sim=True),
        synchrotron=synchrotron,
        xbpm_feedback=xbpm_feedback,
        zebra=i03.zebra(fake_with_ophyd_sim=True),
        zocalo=zocalo,
        panda=MagicMock(),
        panda_fast_grid_scan=i03.panda_fast_grid_scan(fake_with_ophyd_sim=True),
        robot=i03.robot(fake_with_ophyd_sim=True),
    )

    fake_composite.eiger.stage = MagicMock(return_value=done_status)
    # unstage should be mocked on a per-test basis because several rely on unstage
    fake_composite.eiger.set_detector_parameters(test_fgs_params.detector_params)
    fake_composite.eiger.ALL_FRAMES_TIMEOUT = 2  # type: ignore
    fake_composite.eiger.stop_odin_when_all_frames_collected = MagicMock()
    fake_composite.eiger.odin.check_odin_state = lambda: True

    mock_gridscan_kickoff_complete(fake_composite.fast_grid_scan)
    mock_gridscan_kickoff_complete(fake_composite.panda_fast_grid_scan)

    test_result = {
        "centre_of_mass": [6, 6, 6],
        "max_voxel": [5, 5, 5],
        "max_count": 123456,
        "n_voxels": 321,
        "total_count": 999999,
        "bounding_box": [[3, 3, 3], [9, 9, 9]],
    }

    @AsyncStatus.wrap
    async def mock_complete(result):
        await fake_composite.zocalo._put_results([result], {"dcid": 0, "dcgid": 0})

    fake_composite.zocalo.trigger = MagicMock(
        side_effect=partial(mock_complete, test_result)
    )  # type: ignore
    fake_composite.zocalo.timeout_s = 3
    fake_composite.fast_grid_scan.scan_invalid.sim_put(False)  # type: ignore
    fake_composite.fast_grid_scan.position_counter.sim_put(0)  # type: ignore
    fake_composite.smargon.x.max_velocity.sim_put(10)  # type: ignore

    set_sim_value(fake_composite.robot.barcode.bare_signal, ["BARCODE"])

    return fake_composite


def fake_read(obj, initial_positions, _):
    initial_positions[obj] = 0
    yield Msg("null", obj)


def extract_metafile(input_filename, output_filename):
    with gzip.open(input_filename) as metafile_fo:
        with open(output_filename, "wb") as output_fo:
            output_fo.write(metafile_fo.read())


class RunEngineSimulator:
    """This class simulates a Bluesky RunEngine by recording and injecting responses to messages according to the
    bluesky Message Protocol (see bluesky docs for details).
    Basic usage consists of
    1) Registering various handlers to respond to anticipated messages in the experiment plan and fire any
    needed callbacks.
    2) Calling simulate_plan()
    3) Examining the returned message list and making asserts against them"""

    def __init__(self):
        self.message_handlers = []
        self.callbacks = {}
        self.next_callback_token = 0

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
        self,
        commands: Sequence[str],
        obj_name: Optional[str],
        handler: Callable[[Msg], object],
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

    def add_wait_handler(
        self, handler: Callable[[Msg], None], group: str = "any"
    ) -> None:
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

    def fire_callback(self, document_name, document) -> None:
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

    def assert_message_and_return_remaining(
        self,
        messages: list[Msg],
        predicate: Callable[[Msg], bool],
        group: Optional[str] = None,
    ):
        """Find the next message matching the predicate, assert that we found it
        Return: all the remaining messages starting from the matched message"""
        indices = [
            i
            for i in range(len(messages))
            if (
                not group
                or (messages[i].kwargs and messages[i].kwargs.get("group") == group)
            )
            and predicate(messages[i])
        ]
        assert indices, f"Nothing matched predicate {predicate}"
        return messages[indices[0] :]

    def mock_message_generator(
        self,
        function_name: str,
    ) -> Callable[..., Generator[Msg, object, object]]:
        """Returns a callable that returns a generator yielding a Msg object recording the call arguments.
        This can be used to mock methods returning a bluesky plan or portion thereof, call it from within a unit test
        using the RunEngineSimulator, and then perform asserts on the message to verify in-order execution of the plan
        """

        def mock_method(*args, **kwargs):
            yield Msg(function_name, None, *args, **kwargs)

        return mock_method


class MessageHandler:
    def __init__(self, p: Callable[[Msg], bool], r: Callable[[Msg], object]):
        self.predicate = p
        self.runnable = r


@pytest.fixture
def sim_run_engine():
    return RunEngineSimulator()
