from unittest.mock import DEFAULT, MagicMock, patch

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
from ophyd.status import Status

from artemis.experiment_plans.fast_grid_scan_plan import FGSComposite
from artemis.experiment_plans.rotation_scan_plan import rotation_scan_plan
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
def test_rotation_params_nomove():
    return RotationInternalParameters(
        **raw_params_from_file(
            "src/artemis/parameters/tests/test_data/good_test_rotation_scan_parameters_nomove.json"
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


@pytest.fixture()
def fake_create_devices(
    eiger: EigerDetector,
    smargon: Smargon,
    zebra: Zebra,
):
    eiger.stage = MagicMock()
    eiger.unstage = MagicMock()
    mock_omega_sets = MagicMock(return_value=Status(done=True, success=True))

    mock_arm_disarm = MagicMock(
        side_effect=zebra.pc.arm.armed.set, return_value=Status(done=True, success=True)
    )
    zebra.pc.arm.set = mock_arm_disarm
    smargon.omega.velocity.set = mock_omega_sets
    smargon.omega.set = mock_omega_sets

    devices = {
        "eiger": i03.eiger(fake_with_ophyd_sim=True),
        "smargon": smargon,
        "zebra": zebra,
        "detector_motion": i03.detector_motion(fake_with_ophyd_sim=True),
        "backlight": i03.backlight(fake_with_ophyd_sim=True),
    }
    return devices


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


def fake_read(obj, initial_positions, _):
    initial_positions[obj] = 0
    yield Msg("null", obj)


def do_rotation_plan_for_tests(
    run_engine,
    callbacks,
    sim_und,
    sim_synch,
    sim_slits,
    sim_flux,
    sim_att,
    expt_params,
    sim_sgon,
    sim_zeb,
    sim_bl,
    sim_det,
):
    with (
        patch(
            "bluesky.preprocessors.__read_and_stash_a_motor",
            fake_read,
        ),
        patch(
            "artemis.experiment_plans.rotation_scan_plan.RotationCallbackCollection.from_params",
            lambda _: callbacks,
        ),
        patch("dodal.beamlines.i03.undulator", lambda: sim_und),
        patch("dodal.beamlines.i03.synchrotron", lambda: sim_synch),
        patch("dodal.beamlines.i03.s4_slit_gaps", lambda: sim_slits),
        patch("dodal.beamlines.i03.flux", lambda: sim_flux),
        patch("dodal.beamlines.i03.attenuator", lambda: sim_att),
    ):
        run_engine(
            rotation_scan_plan(
                expt_params,
                sim_sgon,
                sim_zeb,
                sim_bl,
                sim_att,
                sim_det,
            )
        )


def setup_and_run_rotation_plan_for_tests(
    RE: RunEngine,
    test_params: RotationInternalParameters,
    smargon: Smargon,
    zebra: Zebra,
    eiger: EigerDetector,
    attenuator: Attenuator,
    detector_motion: DetectorMotion,
    backlight: Backlight,
    mock_rotation_subscriptions: RotationCallbackCollection,
    synchrotron: Synchrotron,
    s4_slit_gaps: S4SlitGaps,
    undulator: Undulator,
    flux: Flux,
):
    from functools import partial

    def side_set_w_return(obj, *args):
        obj.sim_put(*args)
        return DEFAULT

    smargon.omega.velocity.set = MagicMock(
        return_value=Status(done=True, success=True),
        side_effect=partial(side_set_w_return, smargon.omega.velocity),
    )
    smargon.omega.set = MagicMock(
        return_value=Status(done=True, success=True),
        side_effect=partial(side_set_w_return, smargon.omega.user_readback),
    )
    smargon.x.set = MagicMock(
        return_value=Status(done=True, success=True),
        side_effect=partial(side_set_w_return, smargon.x.user_readback),
    )
    smargon.y.set = MagicMock(
        return_value=Status(done=True, success=True),
        side_effect=partial(side_set_w_return, smargon.y.user_readback),
    )
    smargon.z.set = MagicMock(
        return_value=Status(done=True, success=True),
        side_effect=partial(side_set_w_return, smargon.z.user_readback),
    )
    smargon.chi.set = MagicMock(
        return_value=Status(done=True, success=True),
        side_effect=partial(side_set_w_return, smargon.chi.user_readback),
    )
    smargon.phi.set = MagicMock(
        return_value=Status(done=True, success=True),
        side_effect=partial(side_set_w_return, smargon.phi.user_readback),
    )

    mock_arm = MagicMock(
        side_effect=zebra.pc.arm.armed.set, return_value=Status(done=True, success=True)
    )
    zebra.pc.arm.arm_set.set = mock_arm

    with patch("bluesky.plan_stubs.wait", autospec=True):
        do_rotation_plan_for_tests(
            RE,
            mock_rotation_subscriptions,
            undulator,
            synchrotron,
            s4_slit_gaps,
            flux,
            attenuator,
            test_params,
            smargon,
            zebra,
            backlight,
            detector_motion,
        )

    return {
        "RE": RE,
        "test_rotation_params": test_params,
        "smargon": smargon,
        "zebra": zebra,
        "eiger": eiger,
        "attenuator": attenuator,
        "detector_motion": detector_motion,
        "backlight": backlight,
        "mock_rotation_subscriptions": mock_rotation_subscriptions,
        "synchrotron": synchrotron,
        "s4_slit_gaps": s4_slit_gaps,
        "undulator": undulator,
        "flux": flux,
    }


@pytest.fixture
def setup_and_run_rotation_plan_for_tests_standard(
    RE: RunEngine,
    test_rotation_params: RotationInternalParameters,
    smargon: Smargon,
    zebra: Zebra,
    eiger: EigerDetector,
    attenuator: Attenuator,
    detector_motion: DetectorMotion,
    backlight: Backlight,
    mock_rotation_subscriptions: RotationCallbackCollection,
    synchrotron: Synchrotron,
    s4_slit_gaps: S4SlitGaps,
    undulator: Undulator,
    flux: Flux,
):
    return setup_and_run_rotation_plan_for_tests(
        RE,
        test_rotation_params,
        smargon,
        zebra,
        eiger,
        attenuator,
        detector_motion,
        backlight,
        mock_rotation_subscriptions,
        synchrotron,
        s4_slit_gaps,
        undulator,
        flux,
    )


@pytest.fixture
def setup_and_run_rotation_plan_for_tests_nomove(
    RE: RunEngine,
    test_rotation_params_nomove: RotationInternalParameters,
    smargon: Smargon,
    zebra: Zebra,
    eiger: EigerDetector,
    attenuator: Attenuator,
    detector_motion: DetectorMotion,
    backlight: Backlight,
    mock_rotation_subscriptions: RotationCallbackCollection,
    synchrotron: Synchrotron,
    s4_slit_gaps: S4SlitGaps,
    undulator: Undulator,
    flux: Flux,
):
    return setup_and_run_rotation_plan_for_tests(
        RE,
        test_rotation_params_nomove,
        smargon,
        zebra,
        eiger,
        attenuator,
        detector_motion,
        backlight,
        mock_rotation_subscriptions,
        synchrotron,
        s4_slit_gaps,
        undulator,
        flux,
    )
