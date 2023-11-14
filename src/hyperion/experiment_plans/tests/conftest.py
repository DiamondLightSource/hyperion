from functools import partial
from typing import Callable, Generator
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
from dodal.devices.flux import Flux
from dodal.devices.s4_slit_gaps import S4SlitGaps
from dodal.devices.smargon import Smargon
from dodal.devices.synchrotron import Synchrotron
from dodal.devices.undulator import Undulator
from dodal.devices.zebra import Zebra
from ophyd.epics_motor import EpicsMotor
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
from hyperion.external_interaction.system_tests.conftest import TEST_RESULT_LARGE
from hyperion.external_interaction.zocalo.zocalo_interaction import ZocaloInteractor
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
            "src/hyperion/parameters/tests/test_data/good_test_rotation_scan_parameters.json"
        )
    )


@pytest.fixture
def test_rotation_params_nomove():
    return RotationInternalParameters(
        **raw_params_from_file(
            "src/hyperion/parameters/tests/test_data/good_test_rotation_scan_parameters_nomove.json"
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
        "zoom_params_file": "src/hyperion/experiment_plans/tests/test_data/jCameraManZoomLevels.xml",
        "oav_config_json": "src/hyperion/experiment_plans/tests/test_data/OAVCentring.json",
        "display_config": "src/hyperion/experiment_plans/tests/test_data/display.configuration",
    }


@pytest.fixture
def test_full_grid_scan_params():
    params = raw_params_from_file(
        "src/hyperion/parameters/tests/test_data/good_test_grid_with_edge_detect_parameters.json"
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
        subscriptions.ispyb_handler.start(start_doc)
        subscriptions.zocalo_handler.start(start_doc)
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
