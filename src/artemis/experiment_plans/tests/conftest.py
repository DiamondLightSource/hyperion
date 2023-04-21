import pytest
from bluesky.run_engine import RunEngine
from dodal import i03
from dodal.devices.aperturescatterguard import AperturePositions

from artemis.experiment_plans.fast_grid_scan_plan import FGSComposite
from artemis.parameters.external_parameters import from_file as raw_params_from_file
from artemis.parameters.internal_parameters.plan_specific.fgs_internal_params import (
    FGSInternalParameters,
)
from artemis.parameters.internal_parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)


@pytest.fixture
def test_fgs_params():
    return FGSInternalParameters(raw_params_from_file())


@pytest.fixture
def test_rotation_params():
    return RotationInternalParameters(
        raw_params_from_file(
            "src/artemis/parameters/tests/test_data/good_test_rotation_scan_parameters.json"
        )
    )


@pytest.fixture
def fake_fgs_composite(test_fgs_params: FGSInternalParameters):
    fake_composite = FGSComposite(fake=True)
    fake_composite.eiger.set_detector_parameters(
        test_fgs_params.artemis_params.detector_params
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
    fake_composite.aperture_scatterguard.load_aperture_positions(
        AperturePositions(
            LARGE=(1, 2, 3, 4, 5),
            MEDIUM=(2, 3, 3, 5, 6),
            SMALL=(3, 4, 3, 6, 7),
            ROBOT_LOAD=(0, 0, 3, 0, 0),
        )
    )

    fake_composite.fast_grid_scan.scan_invalid.sim_put(False)
    fake_composite.fast_grid_scan.position_counter.sim_put(0)
    return fake_composite


@pytest.fixture
def eiger():
    return i03.eiger(fake_with_ophyd_sim=True)


@pytest.fixture
def smargon():
    smargon = i03.smargon(fake_with_ophyd_sim=True)
    smargon.x.user_setpoint._use_limits = False
    smargon.y.user_setpoint._use_limits = False
    smargon.z.user_setpoint._use_limits = False
    smargon.omega.user_setpoint._use_limits = False
    return smargon


@pytest.fixture
def zebra():
    return i03.zebra(fake_with_ophyd_sim=True)


@pytest.fixture
def RE():
    return RunEngine({})
