import sys
from functools import partial
from os import environ, getenv
from typing import Generator
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
from dodal.devices.fast_grid_scan import GridScanCompleteStatus
from dodal.devices.flux import Flux
from dodal.devices.s4_slit_gaps import S4SlitGaps
from dodal.devices.smargon import Smargon
from dodal.devices.synchrotron import Synchrotron
from dodal.devices.undulator import Undulator
from dodal.devices.zebra import Zebra
from dodal.log import LOGGER as dodal_logger
from ophyd.epics_motor import EpicsMotor
from ophyd.status import DeviceStatus, Status
from ophyd_async.core.async_status import AsyncStatus

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
    set_up_logging_handlers,
)
from hyperion.parameters.external_parameters import from_file as raw_params_from_file
from hyperion.parameters.plan_specific.grid_scan_with_edge_detect_params import (
    GridScanWithEdgeDetectInternalParameters,
)
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)


def _destroy_loggers(loggers):
    for logger in loggers:
        for handler in logger.handlers:
            handler.close()
        logger.handlers.clear()


def pytest_runtest_setup(item):
    markers = [m.name for m in item.own_markers]
    log_level = "DEBUG" if item.config.option.debug_logging else "INFO"
    log_params = {"logging_level": log_level, "dev_mode": True}
    if "skip_log_setup" not in markers:
        if LOGGER.handlers == []:
            if dodal_logger.handlers == []:
                print(f"Initialising Hyperion logger for tests at {log_level}")
                set_up_logging_handlers(logger=LOGGER, **log_params)
        if ISPYB_LOGGER.handlers == []:
            print(f"Initialising ISPyB logger for tests at {log_level}")
            set_up_logging_handlers(
                **log_params,
                filename="hyperion_ispyb_callback.txt",
                logger=ISPYB_LOGGER,
            )
        if NEXUS_LOGGER.handlers == []:
            print(f"Initialising nexus logger for tests at {log_level}")
            set_up_logging_handlers(
                **log_params,
                filename="hyperion_nexus_callback.txt",
                logger=NEXUS_LOGGER,
            )
    else:
        print("Skipping log setup for log test - deleting existing handlers")
        _destroy_loggers([*ALL_LOGGERS, dodal_logger])

    if "s03" in markers:
        print("Running s03 test - setting EPICS server ports variables...")
        s03_epics_server_port = getenv("S03_EPICS_CA_SERVER_PORT")
        s03_epics_repeater_port = getenv("S03_EPICS_CA_REPEATER_PORT")

        assert (
            s03_epics_server_port is not None and s03_epics_repeater_port is not None
        ), (
            "Please run the S03 launch script with the '-f' flag to run it on a port "
            " which doesn't clash with the real EPICS ports."
        )

        environ["EPICS_CA_SERVER_PORT"] = s03_epics_server_port
        print(f"[EPICS_CA_SERVER_PORT] = {s03_epics_server_port}")
        environ["EPICS_CA_REPEATER_PORT"] = s03_epics_repeater_port
        print(f"[EPICS_CA_REPEATER_PORT] = {s03_epics_repeater_port}")


def pytest_runtest_teardown():
    if "dodal.beamlines.beamline_utils" in sys.modules:
        sys.modules["dodal.beamlines.beamline_utils"].clear_devices()


@pytest.fixture
def RE():
    RE = RunEngine({}, call_returns_result=True)
    RE.subscribe(
        VerbosePlanExecutionLoggingCallback()
    )  # log all events at INFO for easier debugging
    return RE


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

    # Initial positions, needed for stub_offsets
    smargon.stub_offsets.center_at_current_position.disp.sim_put(0)  # type: ignore
    smargon.x.user_readback.sim_put(0.0)  # type: ignore
    smargon.y.user_readback.sim_put(0.0)  # type: ignore
    smargon.z.user_readback.sim_put(0.0)  # type: ignore

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
def fake_fgs_composite(
    smargon: Smargon,
    test_fgs_params: GridscanInternalParameters,
    RE: RunEngine,
    done_status,
):
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
        zocalo=i03.zocalo(),
    )

    fake_composite.eiger.stage = MagicMock(return_value=done_status)
    fake_composite.eiger.set_detector_parameters(
        test_fgs_params.hyperion_params.detector_params
    )
    fake_composite.eiger.ALL_FRAMES_TIMEOUT = 2  # type: ignore
    fake_composite.eiger.stop_odin_when_all_frames_collected = MagicMock()
    fake_composite.eiger.odin.check_odin_state = lambda: True
    fake_composite.aperture_scatterguard.aperture.x.user_setpoint._use_limits = False
    fake_composite.aperture_scatterguard.aperture.y.user_setpoint._use_limits = False
    fake_composite.aperture_scatterguard.aperture.z.user_setpoint._use_limits = False
    fake_composite.aperture_scatterguard.scatterguard.x.user_setpoint._use_limits = (
        False
    )
    fake_composite.aperture_scatterguard.scatterguard.y.user_setpoint._use_limits = (
        False
    )
    gridscan_start = DeviceStatus(device=fake_composite.fast_grid_scan)
    gridscan_start.set_finished()
    gridscan_result = GridScanCompleteStatus(device=fake_composite.fast_grid_scan)
    gridscan_result.set_finished()
    fake_composite.fast_grid_scan.kickoff = MagicMock(return_value=gridscan_start)
    fake_composite.fast_grid_scan.complete = MagicMock(return_value=gridscan_result)

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
        await fake_composite.zocalo._put_results([result])

    fake_composite.zocalo.trigger = MagicMock(side_effect=partial(mock_complete, test_result))  # type: ignore
    fake_composite.zocalo.timeout_s = 3
    fake_composite.fast_grid_scan.scan_invalid.sim_put(False)  # type: ignore
    fake_composite.fast_grid_scan.position_counter.sim_put(0)  # type: ignore

    return fake_composite


def fake_read(obj, initial_positions, _):
    initial_positions[obj] = 0
    yield Msg("null", obj)
