from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import DEFAULT, MagicMock, call, patch

import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.attenuator import Attenuator
from dodal.devices.backlight import Backlight
from dodal.devices.DCM import DCM
from dodal.devices.detector_motion import DetectorMotion
from dodal.devices.eiger import EigerDetector
from dodal.devices.flux import Flux
from dodal.devices.s4_slit_gaps import S4SlitGaps
from dodal.devices.smargon import Smargon
from dodal.devices.synchrotron import Synchrotron
from dodal.devices.undulator import Undulator
from dodal.devices.zebra import Zebra
from ophyd.status import Status

from hyperion.experiment_plans.rotation_scan_plan import (
    DEFAULT_DIRECTION,
    DEFAULT_MAX_VELOCITY,
    RotationScanComposite,
    move_to_end_w_buffer,
    move_to_start_w_buffer,
    rotation_scan,
    rotation_scan_plan,
)
from hyperion.external_interaction.callbacks.rotation.callback_collection import (
    RotationCallbackCollection,
)
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)

from .conftest import fake_read

if TYPE_CHECKING:
    from dodal.devices.aperturescatterguard import ApertureScatterguard
    from dodal.devices.attenuator import Attenuator
    from dodal.devices.backlight import Backlight
    from dodal.devices.detector_motion import DetectorMotion
    from dodal.devices.eiger import EigerDetector
    from dodal.devices.smargon import Smargon


TEST_OFFSET = 1
TEST_SHUTTER_OPENING_DEGREES = 2.5


def do_rotation_main_plan_for_tests(
    run_eng_w_subs,
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
    sim_dcm,
    sim_ap_sg,
):
    devices = RotationScanComposite(
        attenuator=sim_att,
        backlight=sim_bl,
        dcm=sim_dcm,
        detector_motion=sim_det,
        eiger=MagicMock(),
        flux=sim_flux,
        smargon=sim_sgon,
        undulator=sim_und,
        synchrotron=sim_synch,
        s4_slit_gaps=sim_slits,
        zebra=sim_zeb,
        aperture_scatterguard=sim_ap_sg,
    )
    run_engine, _ = run_eng_w_subs
    with (
        patch(
            "bluesky.preprocessors.__read_and_stash_a_motor",
            fake_read,
        ),
        patch("dodal.beamlines.i03.undulator", lambda: sim_und),
        patch("dodal.beamlines.i03.synchrotron", lambda: sim_synch),
        patch("dodal.beamlines.i03.s4_slit_gaps", lambda: sim_slits),
        patch("dodal.beamlines.i03.flux", lambda: sim_flux),
        patch("dodal.beamlines.i03.attenuator", lambda: sim_att),
    ):
        run_engine(
            rotation_scan_plan(
                devices,
                expt_params,
            ),
        )


@pytest.fixture
def RE_with_subs(
    RE: RunEngine, mock_rotation_subscriptions: RotationCallbackCollection
):
    for cb in mock_rotation_subscriptions:
        RE.subscribe(cb)
    return RE, mock_rotation_subscriptions


@pytest.fixture
def run_full_rotation_plan(
    RE_with_subs: tuple[RunEngine, RotationCallbackCollection],
    test_rotation_params: RotationInternalParameters,
    attenuator: Attenuator,
    synchrotron: Synchrotron,
    s4_slit_gaps: S4SlitGaps,
    undulator: Undulator,
    flux: Flux,
    fake_create_rotation_devices,
):
    RE, mock_rotation_subscriptions = RE_with_subs
    with patch(
        "bluesky.preprocessors.__read_and_stash_a_motor",
        fake_read,
    ):
        RE(rotation_scan(fake_create_rotation_devices, test_rotation_params))

    return fake_create_rotation_devices


def setup_and_run_rotation_plan_for_tests(
    RE_with_subs: tuple[RunEngine, RotationCallbackCollection],
    test_params: RotationInternalParameters,
    smargon: Smargon,
    zebra: Zebra,
    eiger: EigerDetector,
    attenuator: Attenuator,
    detector_motion: DetectorMotion,
    backlight: Backlight,
    synchrotron: Synchrotron,
    s4_slit_gaps: S4SlitGaps,
    undulator: Undulator,
    flux: Flux,
    dcm: DCM,
    aperture_scatterguard: ApertureScatterguard,
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
        do_rotation_main_plan_for_tests(
            RE_with_subs,
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
            dcm,
            aperture_scatterguard,
        )

    return {
        "RE_with_subs": RE_with_subs,
        "test_rotation_params": test_params,
        "smargon": smargon,
        "zebra": zebra,
        "eiger": eiger,
        "attenuator": attenuator,
        "detector_motion": detector_motion,
        "backlight": backlight,
        "synchrotron": synchrotron,
        "s4_slit_gaps": s4_slit_gaps,
        "undulator": undulator,
        "flux": flux,
    }


@pytest.fixture
def setup_and_run_rotation_plan_for_tests_standard(
    RE_with_subs: tuple[RunEngine, RotationCallbackCollection],
    test_rotation_params: RotationInternalParameters,
    smargon: Smargon,
    zebra: Zebra,
    eiger: EigerDetector,
    attenuator: Attenuator,
    detector_motion: DetectorMotion,
    backlight: Backlight,
    synchrotron: Synchrotron,
    s4_slit_gaps: S4SlitGaps,
    undulator: Undulator,
    flux: Flux,
    dcm: DCM,
    aperture_scatterguard: ApertureScatterguard,
):
    return setup_and_run_rotation_plan_for_tests(
        RE_with_subs,
        test_rotation_params,
        smargon,
        zebra,
        eiger,
        attenuator,
        detector_motion,
        backlight,
        synchrotron,
        s4_slit_gaps,
        undulator,
        flux,
        dcm,
        aperture_scatterguard,
    )


@pytest.fixture
def setup_and_run_rotation_plan_for_tests_nomove(
    RE_with_subs: tuple[RunEngine, RotationCallbackCollection],
    test_rotation_params_nomove: RotationInternalParameters,
    smargon: Smargon,
    zebra: Zebra,
    eiger: EigerDetector,
    attenuator: Attenuator,
    detector_motion: DetectorMotion,
    backlight: Backlight,
    synchrotron: Synchrotron,
    s4_slit_gaps: S4SlitGaps,
    undulator: Undulator,
    flux: Flux,
    dcm: DCM,
    aperture_scatterguard: ApertureScatterguard,
):
    return setup_and_run_rotation_plan_for_tests(
        RE_with_subs,
        test_rotation_params_nomove,
        smargon,
        zebra,
        eiger,
        attenuator,
        detector_motion,
        backlight,
        synchrotron,
        s4_slit_gaps,
        undulator,
        flux,
        dcm,
        aperture_scatterguard,
    )


def test_move_to_start(smargon: Smargon, RE):
    start_angle = 153
    mock_velocity_set = MagicMock(return_value=Status(done=True, success=True))
    with patch.object(smargon.omega.velocity, "set", mock_velocity_set):
        RE(move_to_start_w_buffer(smargon.omega, start_angle, TEST_OFFSET))

    mock_velocity_set.assert_called_with(120)
    assert (
        smargon.omega.user_readback.get()
        == start_angle - TEST_OFFSET * DEFAULT_DIRECTION
    )


def test_move_to_end(smargon: Smargon, RE):
    scan_width = 153
    with patch(
        "bluesky.preprocessors.__read_and_stash_a_motor",
        fake_read,
    ):
        RE(
            move_to_end_w_buffer(
                smargon.omega, scan_width, TEST_OFFSET, TEST_SHUTTER_OPENING_DEGREES
            )
        )

    distance_to_move = (
        scan_width + TEST_SHUTTER_OPENING_DEGREES + TEST_OFFSET * 2
    ) * DEFAULT_DIRECTION

    assert smargon.omega.user_readback.get() == distance_to_move


@patch("dodal.beamlines.beamline_utils.active_device_is_same_type", lambda a, b: True)
@patch("hyperion.experiment_plans.rotation_scan_plan.rotation_scan_plan", autospec=True)
def test_rotation_scan(
    plan: MagicMock,
    RE_with_subs: tuple[RunEngine, RotationCallbackCollection],
    test_rotation_params,
    smargon: Smargon,
    zebra: Zebra,
    eiger: EigerDetector,
    detector_motion: DetectorMotion,
    backlight: Backlight,
    attenuator: Attenuator,
    dcm: DCM,
    aperture_scatterguard: ApertureScatterguard,
):
    RE, mock_rotation_subscriptions = RE_with_subs
    zebra.pc.arm.armed.set(False)
    with (
        patch("dodal.beamlines.i03.smargon", return_value=smargon),
        patch("dodal.beamlines.i03.eiger", return_value=eiger),
        patch("dodal.beamlines.i03.zebra", return_value=zebra),
        patch("dodal.beamlines.i03.attenuator", return_value=attenuator),
        patch("dodal.beamlines.i03.backlight", return_value=backlight),
        patch(
            "hyperion.experiment_plans.rotation_scan_plan.DetectorMotion",
            return_value=detector_motion,
        ),
    ):
        composite = RotationScanComposite(
            attenuator=attenuator,
            backlight=backlight,
            dcm=dcm,
            detector_motion=detector_motion,
            eiger=eiger,
            flux=MagicMock(),
            smargon=smargon,
            undulator=MagicMock(),
            synchrotron=MagicMock(),
            s4_slit_gaps=MagicMock(),
            zebra=zebra,
            aperture_scatterguard=aperture_scatterguard,
        )
        RE(rotation_scan(composite, test_rotation_params))

    eiger.stage.assert_called()
    eiger.unstage.assert_called()


def test_rotation_plan_runs(setup_and_run_rotation_plan_for_tests_standard) -> None:
    RE_with_subs: tuple[
        RunEngine, RotationCallbackCollection
    ] = setup_and_run_rotation_plan_for_tests_standard["RE_with_subs"]
    RE, _ = RE_with_subs
    assert RE._exit_status == "success"


def test_rotation_plan_zebra_settings(
    setup_and_run_rotation_plan_for_tests_standard,
) -> None:
    zebra: Zebra = setup_and_run_rotation_plan_for_tests_standard["zebra"]
    params: RotationInternalParameters = setup_and_run_rotation_plan_for_tests_standard[
        "test_rotation_params"
    ]
    expt_params = params.experiment_params

    assert zebra.pc.gate_start.get() == expt_params.omega_start
    assert zebra.pc.gate_start.get() == expt_params.omega_start
    assert zebra.pc.pulse_start.get() == expt_params.shutter_opening_time_s


def test_rotation_plan_energy_settings(setup_and_run_rotation_plan_for_tests_standard):
    params: RotationInternalParameters = setup_and_run_rotation_plan_for_tests_standard[
        "test_rotation_params"
    ]

    assert (
        params.hyperion_params.detector_params.expected_energy_ev == 100
    )  # from good_test_rotation_scan_parameters.json
    assert (
        params.hyperion_params.detector_params.expected_energy_ev
        == params.hyperion_params.ispyb_params.current_energy_ev
    )


def test_full_rotation_plan_smargon_settings(
    run_full_rotation_plan,
    test_rotation_params,
) -> None:
    smargon: Smargon = run_full_rotation_plan.smargon
    params: RotationInternalParameters = test_rotation_params
    expt_params = params.experiment_params

    omega_set: MagicMock = smargon.omega.set  # type: ignore
    rotation_speed = (
        expt_params.image_width / params.hyperion_params.detector_params.exposure_time
    )

    assert smargon.phi.user_readback.get() == expt_params.phi_start
    assert smargon.chi.user_readback.get() == expt_params.chi_start
    assert smargon.x.user_readback.get() == expt_params.x
    assert smargon.y.user_readback.get() == expt_params.y
    assert smargon.z.user_readback.get() == expt_params.z
    assert omega_set.call_count == 6
    omega_set.assert_has_calls(
        [call(DEFAULT_MAX_VELOCITY), call(rotation_speed), call(DEFAULT_MAX_VELOCITY)],
        any_order=True,
    )


def test_rotation_plan_smargon_doesnt_move_xyz_if_not_given_in_params(
    setup_and_run_rotation_plan_for_tests_nomove,
) -> None:
    smargon: Smargon = setup_and_run_rotation_plan_for_tests_nomove["smargon"]
    params: RotationInternalParameters = setup_and_run_rotation_plan_for_tests_nomove[
        "test_rotation_params"
    ]
    expt_params = params.experiment_params

    assert expt_params.phi_start is None
    assert expt_params.chi_start is None
    assert expt_params.x is None
    assert expt_params.y is None
    assert expt_params.z is None
    assert smargon.phi.user_readback.get() == 0
    assert smargon.chi.user_readback.get() == 0
    assert smargon.x.user_readback.get() == 0
    assert smargon.y.user_readback.get() == 0
    assert smargon.z.user_readback.get() == 0
    smargon.phi.set.assert_not_called()
    smargon.chi.set.assert_not_called()
    smargon.x.set.assert_not_called()
    smargon.y.set.assert_not_called()
    smargon.z.set.assert_not_called()


@patch("hyperion.experiment_plans.rotation_scan_plan.cleanup_plan", autospec=True)
@patch("bluesky.plan_stubs.wait", autospec=True)
def test_cleanup_happens(
    bps_wait: MagicMock,
    cleanup_plan: MagicMock,
    RE_with_subs: tuple[RunEngine, RotationCallbackCollection],
    test_rotation_params,
    smargon: Smargon,
    zebra: Zebra,
    eiger: EigerDetector,
    detector_motion: DetectorMotion,
    backlight: Backlight,
    attenuator: Attenuator,
    dcm: DCM,
    aperture_scatterguard: ApertureScatterguard,
):
    RE, mock_rotation_subscriptions = RE_with_subs

    class MyTestException(Exception):
        pass

    smargon.omega.set = MagicMock(
        side_effect=MyTestException("Experiment fails because this is a test")
    )

    composite = RotationScanComposite(
        attenuator=attenuator,
        backlight=backlight,
        dcm=dcm,
        detector_motion=detector_motion,
        eiger=eiger,
        flux=MagicMock(),
        smargon=smargon,
        undulator=MagicMock(),
        synchrotron=MagicMock(),
        s4_slit_gaps=MagicMock(),
        zebra=zebra,
        aperture_scatterguard=aperture_scatterguard,
    )

    # check main subplan part fails
    with pytest.raises(MyTestException):
        RE(
            rotation_scan_plan(
                composite,
                test_rotation_params,
            )
        )
        cleanup_plan.assert_not_called()
    # check that failure is handled in composite plan
    with pytest.raises(MyTestException) as exc:
        RE(
            rotation_scan(
                composite,
                test_rotation_params,
            )
        )
        assert "Experiment fails because this is a test" in exc.value.args[0]
        cleanup_plan.assert_called_once()


@patch(
    "hyperion.experiment_plans.rotation_scan_plan.move_to_start_w_buffer", autospec=True
)
def test_acceleration_offset_calculated_correctly(
    mock_move_to_start: MagicMock,
    RE_with_subs: tuple[RunEngine, RotationCallbackCollection],
    test_rotation_params: RotationInternalParameters,
    smargon: Smargon,
    zebra: Zebra,
    eiger: EigerDetector,
    attenuator: Attenuator,
    detector_motion: DetectorMotion,
    backlight: Backlight,
    synchrotron: Synchrotron,
    s4_slit_gaps: S4SlitGaps,
    undulator: Undulator,
    flux: Flux,
    dcm: DCM,
    aperture_scatterguard: ApertureScatterguard,
):
    smargon.omega.acceleration.sim_put(0.2)  # type: ignore
    setup_and_run_rotation_plan_for_tests(
        RE_with_subs,
        test_rotation_params,
        smargon,
        zebra,
        eiger,
        attenuator,
        detector_motion,
        backlight,
        synchrotron,
        s4_slit_gaps,
        undulator,
        flux,
        dcm,
        aperture_scatterguard,
    )

    expected_start_angle = (
        test_rotation_params.hyperion_params.detector_params.omega_start
    )

    mock_move_to_start.assert_called_once_with(
        smargon.omega, expected_start_angle, pytest.approx(0.3)
    )
