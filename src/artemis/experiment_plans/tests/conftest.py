from unittest.mock import MagicMock

import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.aperturescatterguard import AperturePositions

from artemis.experiment_plans.fast_grid_scan_plan import FGSComposite
from artemis.external_interaction.callbacks.fgs.fgs_callback_collection import (
    FGSCallbackCollection,
)
from artemis.external_interaction.system_tests.conftest import TEST_RESULT_LARGE
from artemis.parameters.external_parameters import from_file as default_raw_params
from artemis.parameters.internal_parameters.internal_parameters import (
    InternalParameters,
)
from artemis.parameters.internal_parameters.plan_specific.fgs_internal_params import (
    FGSInternalParameters,
)


@pytest.fixture()
def test_config_files():
    return {
        "zoom_params_file": "src/artemis/experiment_plans/tests/test_data/jCameraManZoomLevels.xml",
        "oav_config_json": "src/artemis/experiment_plans/tests/test_data/OAVCentring.json",
        "display_config": "src/artemis/experiment_plans/tests/test_data/display.configuration",
    }


@pytest.fixture
def RE():
    return RunEngine({})


@pytest.fixture
def test_params():
    return FGSInternalParameters(default_raw_params())


@pytest.fixture
def fake_fgs_composite(test_params: InternalParameters):
    fake_composite = FGSComposite(
        name="fgs",
        aperture_positions=AperturePositions(
            LARGE=(1, 2, 3, 4, 5),
            MEDIUM=(2, 3, 3, 5, 6),
            SMALL=(3, 4, 3, 6, 7),
            ROBOT_LOAD=(0, 0, 3, 0, 0),
        ),
        detector_params=test_params.artemis_params.detector_params,
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

    return fake_composite


@pytest.fixture
def mock_subscriptions(test_params):
    subscriptions = FGSCallbackCollection.from_params(test_params)
    subscriptions.zocalo_handler.zocalo_interactor.wait_for_result = MagicMock()
    subscriptions.zocalo_handler.zocalo_interactor.run_end = MagicMock()
    subscriptions.zocalo_handler.zocalo_interactor.run_start = MagicMock()
    subscriptions.zocalo_handler.zocalo_interactor.wait_for_result.return_value = (
        TEST_RESULT_LARGE
    )

    subscriptions.nexus_handler.nxs_writer_1 = MagicMock()
    subscriptions.nexus_handler.nxs_writer_2 = MagicMock()

    subscriptions.ispyb_handler.ispyb = MagicMock()
    subscriptions.ispyb_handler.ispyb_ids = [[0, 0], 0, 0]

    return subscriptions
