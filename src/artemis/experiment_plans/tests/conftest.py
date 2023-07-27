from unittest.mock import MagicMock, patch

import pytest
from bluesky.run_engine import RunEngine
from dodal.beamlines import i03
from dodal.devices.aperturescatterguard import AperturePositions
from dodal.devices.smargon import Smargon
from ophyd.status import Status

from artemis.experiment_plans.fast_grid_scan_plan import FGSComposite
from artemis.external_interaction.callbacks.fgs.fgs_callback_collection import (
    FGSCallbackCollection,
)
from artemis.external_interaction.callbacks.rotation.rotation_callback_collection import (
    RotationCallbackCollection,
)
from artemis.external_interaction.ispyb.store_in_ispyb import Store3DGridscanInIspyb
from artemis.external_interaction.system_tests.conftest import TEST_RESULT_LARGE
from artemis.parameters.external_parameters import from_file as raw_params_from_file
from artemis.parameters.internal_parameters import InternalParameters
from artemis.parameters.plan_specific.fgs_internal_params import FGSInternalParameters
from artemis.parameters.plan_specific.grid_scan_with_edge_detect_params import (
    GridScanWithEdgeDetectInternalParameters,
)
from artemis.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)


@pytest.fixture
def test_fgs_params():
    return FGSInternalParameters(**raw_params_from_file())


@pytest.fixture
def test_rotation_params():
    return RotationInternalParameters(
        **raw_params_from_file(
            "src/artemis/parameters/tests/test_data/good_test_rotation_scan_parameters.json"
        )
    )


@pytest.fixture
def eiger():
    return i03.eiger(fake_with_ophyd_sim=True)


@pytest.fixture
def smargon() -> Smargon:
    smargon = i03.smargon(fake_with_ophyd_sim=True)
    smargon.x.user_setpoint._use_limits = False
    smargon.y.user_setpoint._use_limits = False
    smargon.z.user_setpoint._use_limits = False
    smargon.omega.user_setpoint._use_limits = False

    def mock_omega_set(val):
        smargon.omega.user_readback.sim_put(val)
        return Status(done=True, success=True)

    with patch.object(smargon.omega, "set", mock_omega_set):
        yield smargon


@pytest.fixture
def zebra():
    return i03.zebra(fake_with_ophyd_sim=True)


@pytest.fixture
def backlight():
    return i03.backlight(fake_with_ophyd_sim=True)


@pytest.fixture
def detector_motion():
    return i03.detector_motion(fake_with_ophyd_sim=True)


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
def flux():
    return i03.flux(fake_with_ophyd_sim=True)


@pytest.fixture
def attenuator():
    return i03.attenuator(fake_with_ophyd_sim=True)


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
    return RunEngine({})


@pytest.fixture()
def test_config_files():
    return {
        "zoom_params_file": "src/artemis/experiment_plans/tests/test_data/jCameraManZoomLevels.xml",
        "oav_config_json": "src/artemis/experiment_plans/tests/test_data/OAVCentring.json",
        "display_config": "src/artemis/experiment_plans/tests/test_data/display.configuration",
    }


@pytest.fixture
def test_full_grid_scan_params():
    params = raw_params_from_file(
        "src/artemis/parameters/tests/test_data/good_test_grid_with_edge_detect_parameters.json"
    )
    return GridScanWithEdgeDetectInternalParameters(**params)


@pytest.fixture
def fake_fgs_composite(smargon: Smargon, test_fgs_params: InternalParameters):
    fake_composite = FGSComposite(
        aperture_positions=AperturePositions(
            LARGE=(1, 2, 3, 4, 5),
            MEDIUM=(2, 3, 3, 5, 6),
            SMALL=(3, 4, 3, 6, 7),
            ROBOT_LOAD=(0, 0, 3, 0, 0),
        ),
        detector_params=test_fgs_params.artemis_params.detector_params,
        fake=True,
    )
    fake_composite.aperture_scatterguard.aperture.x.user_setpoint._use_limits = False
    fake_composite.aperture_scatterguard.aperture.y.user_setpoint._use_limits = False
    fake_composite.aperture_scatterguard.aperture.z.user_setpoint._use_limits = False
    fake_composite.aperture_scatterguard.scatterguard.x.user_setpoint._use_limits = (
        False
    )
    fake_composite.aperture_scatterguard.scatterguard.y.user_setpoint._use_limits = (
        False
    )

    fake_composite.fast_grid_scan.scan_invalid.sim_put(False)
    fake_composite.fast_grid_scan.position_counter.sim_put(0)

    fake_composite.sample_motors = smargon

    return fake_composite


@pytest.fixture
def mock_subscriptions(test_fgs_params):
    subscriptions = FGSCallbackCollection.from_params(test_fgs_params)
    subscriptions.zocalo_handler.zocalo_interactor.wait_for_result = MagicMock()
    subscriptions.zocalo_handler.zocalo_interactor.run_end = MagicMock()
    subscriptions.zocalo_handler.zocalo_interactor.run_start = MagicMock()
    subscriptions.zocalo_handler.zocalo_interactor.wait_for_result.return_value = (
        TEST_RESULT_LARGE
    )
    subscriptions.ispyb_handler.ispyb = MagicMock(spec=Store3DGridscanInIspyb)
    subscriptions.ispyb_handler.ispyb.begin_deposition = lambda: [[0, 0], 0, 0]

    return subscriptions


@pytest.fixture
def mock_rotation_subscriptions(test_rotation_params):
    with patch(
        "artemis.external_interaction.callbacks.rotation.rotation_callback_collection.RotationNexusFileHandlerCallback"
    ), patch(
        "artemis.external_interaction.callbacks.rotation.rotation_callback_collection.RotationISPyBHandlerCallback"
    ):
        subscriptions = RotationCallbackCollection.from_params(test_rotation_params)
    return subscriptions
