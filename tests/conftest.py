import asyncio
import gzip
import json
import logging
import sys
import threading
from functools import partial
from typing import Any, Generator, Sequence
from unittest.mock import MagicMock, patch

import bluesky.plan_stubs as bps
import numpy as np
import pytest
from bluesky.run_engine import RunEngine
from bluesky.simulators import RunEngineSimulator
from bluesky.utils import Msg
from dodal.beamlines import i03
from dodal.common.beamlines import beamline_utils
from dodal.common.beamlines.beamline_parameters import (
    GDABeamlineParameters,
)
from dodal.common.beamlines.beamline_utils import clear_devices
from dodal.devices.aperturescatterguard import (
    ApertureFiveDimensionalLocation,
    AperturePosition,
    ApertureScatterguard,
    ApertureScatterguardTolerances,
    SingleAperturePosition,
)
from dodal.devices.attenuator import Attenuator
from dodal.devices.backlight import Backlight
from dodal.devices.dcm import DCM
from dodal.devices.detector.detector_motion import DetectorMotion
from dodal.devices.eiger import EigerDetector
from dodal.devices.fast_grid_scan import FastGridScanCommon
from dodal.devices.flux import Flux
from dodal.devices.oav.oav_detector import OAV, OAVConfigParams
from dodal.devices.oav.oav_parameters import OAVParameters
from dodal.devices.robot import BartRobot
from dodal.devices.s4_slit_gaps import S4SlitGaps
from dodal.devices.smargon import Smargon
from dodal.devices.synchrotron import Synchrotron, SynchrotronMode
from dodal.devices.thawer import Thawer
from dodal.devices.undulator import Undulator
from dodal.devices.util.test_utils import patch_motor as oa_patch_motor
from dodal.devices.webcam import Webcam
from dodal.devices.zebra import Zebra
from dodal.log import LOGGER as dodal_logger
from dodal.log import set_up_all_logging_handlers
from ophyd.sim import NullStatus
from ophyd_async.core import Device, DeviceVector, callback_on_mock_put, set_mock_value
from ophyd_async.core.async_status import AsyncStatus
from ophyd_async.epics.motion.motor import Motor
from ophyd_async.epics.signal import epics_signal_rw
from ophyd_async.panda._common_blocks import DatasetTable
from scanspec.core import Path as ScanPath
from scanspec.specs import Line

from hyperion.experiment_plans.flyscan_xray_centre_plan import (
    FlyScanXRayCentreComposite,
)
from hyperion.experiment_plans.rotation_scan_plan import RotationScanComposite
from hyperion.external_interaction.callbacks.logging_callback import (
    VerbosePlanExecutionLoggingCallback,
)
from hyperion.external_interaction.config_server import FeatureFlags
from hyperion.log import (
    ALL_LOGGERS,
    ISPYB_LOGGER,
    LOGGER,
    NEXUS_LOGGER,
    _get_logging_dir,
    do_default_logging_setup,
)
from hyperion.parameters.gridscan import GridScanWithEdgeDetect, ThreeDGridScan
from hyperion.parameters.rotation import MultiRotationScan, RotationScan

i03.DAQ_CONFIGURATION_PATH = "tests/test_data/test_daq_configuration"


def raw_params_from_file(filename):
    with open(filename) as f:
        return json.loads(f.read())


def default_raw_params():
    return raw_params_from_file(
        "tests/test_data/parameter_json_files/test_gridscan_param_defaults.json"
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
    if "dodal.common.beamlines.beamline_utils" in sys.modules:
        sys.modules["dodal.common.beamlines.beamline_utils"].clear_devices()
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


def pass_on_mock(motor, call_log: MagicMock | None = None):
    def _pass_on_mock(value, **kwargs):
        set_mock_value(motor.user_readback, value)
        if call_log is not None:
            call_log(value, **kwargs)

    return _pass_on_mock


def patch_async_motor(
    motor: Motor, initial_position=0, call_log: MagicMock | None = None
):
    set_mock_value(motor.user_setpoint, initial_position)
    set_mock_value(motor.user_readback, initial_position)
    set_mock_value(motor.deadband, 0.001)
    set_mock_value(motor.motor_done_move, 1)
    set_mock_value(motor.velocity, 1)
    return callback_on_mock_put(motor.user_setpoint, pass_on_mock(motor, call_log))


@pytest.fixture
def beamline_parameters():
    return GDABeamlineParameters.from_file(
        "tests/test_data/test_beamline_parameters.txt"
    )


@pytest.fixture
def test_fgs_params():
    return ThreeDGridScan(
        **raw_params_from_file(
            "tests/test_data/parameter_json_files/good_test_parameters.json"
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
            "tests/test_data/parameter_json_files/good_test_rotation_scan_parameters.json"
        )
    )


@pytest.fixture
def test_rotation_params_nomove():
    return RotationScan(
        **raw_params_from_file(
            "tests/test_data/parameter_json_files/good_test_rotation_scan_parameters_nomove.json"
        )
    )


@pytest.fixture
def test_multi_rotation_params():
    return MultiRotationScan(
        **raw_params_from_file(
            "tests/test_data/parameter_json_files/good_test_multi_rotation_scan_parameters.json"
        )
    )


@pytest.fixture
def done_status():
    return NullStatus()


@pytest.fixture
def eiger(done_status):
    eiger = i03.eiger(fake_with_ophyd_sim=True)
    eiger.stage = MagicMock(return_value=done_status)
    eiger.do_arm.set = MagicMock(return_value=done_status)
    eiger.unstage = MagicMock(return_value=done_status)
    return eiger


@pytest.fixture
def smargon(RE: RunEngine) -> Generator[Smargon, None, None]:
    smargon = i03.smargon(fake_with_ophyd_sim=True)
    # Initial positions, needed for stub_offsets
    set_mock_value(smargon.stub_offsets.center_at_current_position.disp, 0)
    set_mock_value(smargon.x.user_readback, 0.0)
    set_mock_value(smargon.y.user_readback, 0.0)
    set_mock_value(smargon.z.user_readback, 0.0)
    set_mock_value(smargon.x.high_limit_travel, 2)
    set_mock_value(smargon.x.low_limit_travel, -2)

    with (
        patch_async_motor(smargon.omega),
        patch_async_motor(smargon.x),
        patch_async_motor(smargon.y),
        patch_async_motor(smargon.z),
        patch_async_motor(smargon.chi),
        patch_async_motor(smargon.phi),
    ):
        yield smargon
    clear_devices()


@pytest.fixture
def zebra():
    RunEngine()
    zebra = i03.zebra(fake_with_ophyd_sim=True)

    def mock_side(*args, **kwargs):
        set_mock_value(zebra.pc.arm.armed, *args, **kwargs)
        return NullStatus()

    zebra.pc.arm.set = MagicMock(side_effect=mock_side)
    return zebra


@pytest.fixture
def backlight():
    return i03.backlight(fake_with_ophyd_sim=True)


@pytest.fixture
def fast_grid_scan():
    return i03.zebra_fast_grid_scan(fake_with_ophyd_sim=True)


@pytest.fixture
def detector_motion(RE):
    det = i03.detector_motion(fake_with_ophyd_sim=True)
    with patch_async_motor(det.z):
        yield det


@pytest.fixture
def undulator():
    return i03.undulator(fake_with_ophyd_sim=True)


@pytest.fixture
def s4_slit_gaps():
    return i03.s4_slit_gaps(fake_with_ophyd_sim=True)


@pytest.fixture
def synchrotron(RE):
    synchrotron = i03.synchrotron(fake_with_ophyd_sim=True)
    set_mock_value(synchrotron.synchrotron_mode, SynchrotronMode.USER)
    set_mock_value(synchrotron.top_up_start_countdown, 10)
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
    set_mock_value(robot.barcode, "BARCODE")
    robot.set = MagicMock(return_value=done_status)
    return robot


@pytest.fixture
def attenuator(RE):
    attenuator = i03.attenuator(fake_with_ophyd_sim=True)
    set_mock_value(attenuator.actual_transmission, 0.49118047952)

    @AsyncStatus.wrap
    async def fake_attenuator_set(val):
        set_mock_value(attenuator.actual_transmission, val)

    attenuator.set = MagicMock(side_effect=fake_attenuator_set)

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
    set_mock_value(dcm.energy_in_kev.user_readback, 12.7)
    set_mock_value(dcm.pitch_in_mrad.user_readback, 1)
    return dcm


@pytest.fixture
def vfm(RE):
    vfm = i03.vfm(fake_with_ophyd_sim=True)
    vfm.bragg_to_lat_lookup_table_path = (
        "tests/test_data/test_beamline_vfm_lat_converter.txt"
    )
    return vfm


@pytest.fixture
def lower_gonio(RE):
    lower_gonio = i03.lower_gonio(fake_with_ophyd_sim=True)
    with (
        oa_patch_motor(lower_gonio.x),
        oa_patch_motor(lower_gonio.y),
        oa_patch_motor(lower_gonio.z),
    ):
        yield lower_gonio


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
def thawer(RE) -> Generator[Thawer, Any, Any]:
    yield i03.thawer(fake_with_ophyd_sim=True)


@pytest.fixture
def aperture_scatterguard(RE):
    positions = {
        AperturePosition.LARGE: SingleAperturePosition(
            location=ApertureFiveDimensionalLocation(0, 1, 2, 3, 4),
            name="Large",
            GDA_name="LARGE_APERTURE",
            radius_microns=100,
        ),
        AperturePosition.MEDIUM: SingleAperturePosition(
            location=ApertureFiveDimensionalLocation(5, 6, 2, 8, 9),
            name="Medium",
            GDA_name="MEDIUM_APERTURE",
            radius_microns=50,
        ),
        AperturePosition.SMALL: SingleAperturePosition(
            location=ApertureFiveDimensionalLocation(10, 11, 2, 13, 14),
            name="Small",
            GDA_name="SMALL_APERTURE",
            radius_microns=20,
        ),
        AperturePosition.ROBOT_LOAD: SingleAperturePosition(
            location=ApertureFiveDimensionalLocation(15, 16, 2, 18, 19),
            name="Robot_load",
            GDA_name="ROBOT_LOAD",
            radius_microns=None,
        ),
    }
    with patch(
        "dodal.beamlines.i03.load_positions_from_beamline_parameters",
        return_value=positions,
    ), patch(
        "dodal.beamlines.i03.load_tolerances_from_beamline_params",
        return_value=ApertureScatterguardTolerances(0.1, 0.1, 0.1, 0.1, 0.1),
    ):
        ap_sg = i03.aperture_scatterguard(fake_with_ophyd_sim=True)
    with (
        patch_async_motor(ap_sg._aperture.x),
        patch_async_motor(ap_sg._aperture.y),
        patch_async_motor(ap_sg._aperture.z, 2),
        patch_async_motor(ap_sg._scatterguard.x),
        patch_async_motor(ap_sg._scatterguard.y),
    ):
        RE(bps.abs_set(ap_sg, AperturePosition.SMALL))

        set_mock_value(ap_sg._aperture.small, 1)
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
        "tests/test_data/parameter_json_files/good_test_grid_with_edge_detect_parameters.json"
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
    mock_omega_sets = MagicMock(return_value=NullStatus())

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
    oav: OAV,
):
    set_mock_value(smargon.omega.max_velocity, 131)
    oav.zoom_controller.onst.sim_put("1.0x")  # type: ignore
    oav.zoom_controller.fvst.sim_put("5.0x")  # type: ignore

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
        oav=oav,
    )


@pytest.fixture
def zocalo(done_status):
    zoc = i03.zocalo(fake_with_ophyd_sim=True)
    zoc.stage = MagicMock(return_value=done_status)
    zoc.unstage = MagicMock(return_value=done_status)
    return zoc


@pytest.fixture
async def panda(RE: RunEngine):
    class MockBlock(Device):
        def __init__(
            self, prefix: str, name: str = "", attributes: dict[str, Any] = {}
        ):
            for name, dtype in attributes.items():
                setattr(self, name, epics_signal_rw(dtype, "", ""))

    def mock_vector_block(n, attributes):
        return DeviceVector(
            {i: MockBlock(f"{i}", f"{i}", attributes) for i in range(n)}
        )

    async def set_mock_blocks(
        panda, mock_blocks: dict[str, tuple[int, dict[str, Any]]]
    ):
        for name, block in mock_blocks.items():
            n, attrs = block
            block = mock_vector_block(n, attrs)
            await block.connect(mock=True)
            setattr(panda, name, block)

    async def create_mock_signals(devices_and_signals: dict[Device, dict[str, Any]]):
        for device, signals in devices_and_signals.items():
            for name, dtype in signals.items():
                sig = epics_signal_rw(dtype, name, name)
                await sig.connect(mock=True)
                setattr(device, name, sig)

    panda = i03.panda(fake_with_ophyd_sim=True)
    await set_mock_blocks(
        panda,
        {
            "inenc": (8, {"setp": float}),
            "clock": (8, {"period": float}),
            "counter": (8, {"enable": str}),
        },
    )
    await create_mock_signals(
        {
            panda.pcap: {"enable": str},
            **{panda.pulse[i]: {"enable": str} for i in panda.pulse.keys()},
        }
    )

    set_mock_value(
        panda.data.datasets, DatasetTable(name=np.array(["name"]), hdf5_type=[])
    )

    return panda


@pytest.fixture
def oav_parameters_for_rotation(test_config_files) -> OAVParameters:
    return OAVParameters(oav_config_json=test_config_files["oav_config_json"])


async def async_status_done():
    await asyncio.sleep(0)


def mock_gridscan_kickoff_complete(gridscan: FastGridScanCommon):
    gridscan.kickoff = MagicMock(return_value=async_status_done)
    gridscan.complete = MagicMock(return_value=async_status_done)


@pytest.fixture
async def fake_fgs_composite(
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
    panda,
):
    fake_composite = FlyScanXRayCentreComposite(
        aperture_scatterguard=aperture_scatterguard,
        attenuator=attenuator,
        backlight=i03.backlight(fake_with_ophyd_sim=True),
        dcm=dcm,
        # We don't use the eiger fixture here because .unstage() is used in some tests
        eiger=i03.eiger(fake_with_ophyd_sim=True),
        zebra_fast_grid_scan=i03.zebra_fast_grid_scan(fake_with_ophyd_sim=True),
        flux=i03.flux(fake_with_ophyd_sim=True),
        s4_slit_gaps=i03.s4_slit_gaps(fake_with_ophyd_sim=True),
        smargon=smargon,
        undulator=i03.undulator(fake_with_ophyd_sim=True),
        synchrotron=synchrotron,
        xbpm_feedback=xbpm_feedback,
        zebra=i03.zebra(fake_with_ophyd_sim=True),
        zocalo=zocalo,
        panda=panda,
        panda_fast_grid_scan=i03.panda_fast_grid_scan(fake_with_ophyd_sim=True),
        robot=i03.robot(fake_with_ophyd_sim=True),
    )

    fake_composite.eiger.stage = MagicMock(return_value=done_status)
    # unstage should be mocked on a per-test basis because several rely on unstage
    fake_composite.eiger.set_detector_parameters(test_fgs_params.detector_params)
    fake_composite.eiger.ALL_FRAMES_TIMEOUT = 2  # type: ignore
    fake_composite.eiger.stop_odin_when_all_frames_collected = MagicMock()
    fake_composite.eiger.odin.check_odin_state = lambda: True

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
    set_mock_value(fake_composite.zebra_fast_grid_scan.scan_invalid, False)
    set_mock_value(fake_composite.zebra_fast_grid_scan.position_counter, 0)
    set_mock_value(fake_composite.smargon.x.max_velocity, 10)

    set_mock_value(fake_composite.robot.barcode, "BARCODE")

    return fake_composite


def fake_read(obj, initial_positions, _):
    initial_positions[obj] = 0
    yield Msg("null", obj)


def extract_metafile(input_filename, output_filename):
    with gzip.open(input_filename) as metafile_fo:
        with open(output_filename, "wb") as output_fo:
            output_fo.write(metafile_fo.read())


@pytest.fixture
def sim_run_engine():
    return RunEngineSimulator()


class DocumentCapturer:
    """A utility which can be subscribed to the RunEngine in place of a callback in order
    to intercept documents and make assertions about their contents"""

    def __init__(self) -> None:
        self.docs_received: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.docs_received.append((args[0], args[1]))

    @staticmethod
    def is_match(
        doc: tuple[str, dict[str, Any]],
        name: str,
        has_fields: Sequence[str] = [],
        matches_fields: dict[str, Any] = {},
    ):
        """Returns True if the given document:
        - has the same name
        - contains all the fields in has_fields
        - contains all the fields in matches_fields with the same content"""

        return (
            doc[0] == name
            and all(f in doc[1].keys() for f in has_fields)
            and matches_fields.items() <= doc[1].items()
        )

    @staticmethod
    def get_matches(
        docs: list[tuple[str, dict[str, Any]]],
        name: str,
        has_fields: Sequence[str] = [],
        matches_fields: dict[str, Any] = {},
    ):
        """Get all the docs from docs which:
        - have the same name
        - contain all the fields in has_fields
        - contain all the fields in matches_fields with the same content"""
        return list(
            filter(
                partial(
                    DocumentCapturer.is_match,
                    name=name,
                    has_fields=has_fields,
                    matches_fields=matches_fields,
                ),
                docs,
            )
        )

    @staticmethod
    def assert_doc(
        docs: list[tuple[str, dict[str, Any]]],
        name: str,
        has_fields: Sequence[str] = [],
        matches_fields: dict[str, Any] = {},
        does_exist: bool = True,
    ):
        """Assert that a matching doc has been recieved by the sim,
        and returns the first match if it is meant to exist"""
        matches = DocumentCapturer.get_matches(docs, name, has_fields, matches_fields)
        if does_exist:
            assert matches
            return matches[0]
        else:
            assert matches == []

    @staticmethod
    def get_docs_until(
        docs: list[tuple[str, dict[str, Any]]],
        name: str,
        has_fields: Sequence[str] = [],
        matches_fields: dict[str, Any] = {},
    ):
        """return all the docs from the list of docs until the first matching one"""
        for i, doc in enumerate(docs):
            if DocumentCapturer.is_match(doc, name, has_fields, matches_fields):
                return docs[: i + 1]
        raise ValueError(f"Doc {name=}, {has_fields=}, {matches_fields=} not found")

    @staticmethod
    def get_docs_from(
        docs: list[tuple[str, dict[str, Any]]],
        name: str,
        has_fields: Sequence[str] = [],
        matches_fields: dict[str, Any] = {},
    ):
        """return all the docs from the list of docs after the first matching one"""
        for i, doc in enumerate(docs):
            if DocumentCapturer.is_match(doc, name, has_fields, matches_fields):
                return docs[i:]
        raise ValueError(f"Doc {name=}, {has_fields=}, {matches_fields=} not found")

    @staticmethod
    def assert_events_and_data_in_order(
        docs: list[tuple[str, dict[str, Any]]],
        match_data_keys_list: Sequence[Sequence[str]],
    ):
        for event_data_keys in match_data_keys_list:
            docs = DocumentCapturer.get_docs_from(docs, "event")
            doc = docs.pop(0)[1]["data"]
            assert all(
                k in doc.keys() for k in event_data_keys
            ), f"One of {event_data_keys=} not in {doc}"


@pytest.fixture
def feature_flags():
    return FeatureFlags(
        **{field_name: False for field_name in FeatureFlags.__fields__.keys()}
    )
