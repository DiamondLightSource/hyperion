from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import DEFAULT, MagicMock, call, patch

import pytest
from bluesky.run_engine import RunEngine
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

from hyperion.experiment_plans.rotation_scan_plan import (
    DEFAULT_DIRECTION,
    DEFAULT_MAX_VELOCITY,
    RotationScanComposite,
    move_to_end_w_buffer,
    move_to_start_w_buffer,
    rotation_scan,
    rotation_scan_plan,
)
from hyperion.experiment_plans.tests.conftest import fake_read
from hyperion.external_interaction.callbacks.rotation.callback_collection import (
    RotationCallbackCollection,
)
from hyperion.parameters.constants import DEV_ISPYB_DATABASE_CFG
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)
from hyperion.utils.utils import convert_angstrom_to_eV

if TYPE_CHECKING:
    from dodal.devices.attenuator import Attenuator
    from dodal.devices.backlight import Backlight
    from dodal.devices.detector_motion import DetectorMotion
    from dodal.devices.eiger import EigerDetector
    from dodal.devices.smargon import Smargon


TEST_OFFSET = 1
TEST_SHUTTER_OPENING_DEGREES = 2.5


def do_rotation_main_plan_for_tests(
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
    devices = RotationScanComposite(
        attenuator=sim_att,
        backlight=sim_bl,
        detector_motion=sim_det,
        eiger=MagicMock(),
        flux=sim_flux,
        smargon=sim_sgon,
        undulator=sim_und,
        synchrotron=sim_synch,
        s4_slit_gaps=sim_slits,
        zebra=sim_zeb,
    )

    with (
        patch(
            "bluesky.preprocessors.__read_and_stash_a_motor",
            fake_read,
        ),
        patch(
            "hyperion.experiment_plans.rotation_scan_plan.RotationCallbackCollection.from_params",
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
                devices,
                expt_params,
            ),
        )


@pytest.fixture
def run_full_rotation_plan(
    RE: RunEngine,
    test_rotation_params: RotationInternalParameters,
    fake_create_rotation_devices,
    attenuator: Attenuator,
    mock_rotation_subscriptions: RotationCallbackCollection,
    synchrotron: Synchrotron,
    s4_slit_gaps: S4SlitGaps,
    undulator: Undulator,
    flux: Flux,
):
    with (
        patch(
            "bluesky.preprocessors.__read_and_stash_a_motor",
            fake_read,
        ),
        patch(
            "hyperion.experiment_plans.rotation_scan_plan.RotationCallbackCollection.from_params",
            lambda _: mock_rotation_subscriptions,
        ),
    ):
        RE(rotation_scan(fake_create_rotation_devices, test_rotation_params))

    return fake_create_rotation_devices


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
        do_rotation_main_plan_for_tests(
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
    RE,
    test_rotation_params,
    smargon: Smargon,
    zebra: Zebra,
    eiger: EigerDetector,
    detector_motion: DetectorMotion,
    backlight: Backlight,
    attenuator: Attenuator,
    mock_rotation_subscriptions: RotationCallbackCollection,
):
    eiger.stage = MagicMock()
    eiger.unstage = MagicMock()
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
        patch(
            "hyperion.experiment_plans.rotation_scan_plan.RotationCallbackCollection.from_params",
            lambda _: mock_rotation_subscriptions,
        ),
    ):
        composite = RotationScanComposite(
            attenuator=attenuator,
            backlight=backlight,
            detector_motion=detector_motion,
            eiger=eiger,
            flux=MagicMock(),
            smargon=smargon,
            undulator=MagicMock(),
            synchrotron=MagicMock(),
            s4_slit_gaps=MagicMock(),
            zebra=zebra,
        )
        RE(rotation_scan(composite, test_rotation_params))

    eiger.stage.assert_called()
    eiger.unstage.assert_called()


def test_rotation_plan_runs(setup_and_run_rotation_plan_for_tests_standard):
    RE: RunEngine = setup_and_run_rotation_plan_for_tests_standard["RE"]
    assert RE._exit_status == "success"


def test_rotation_plan_zebra_settings(setup_and_run_rotation_plan_for_tests_standard):
    zebra: Zebra = setup_and_run_rotation_plan_for_tests_standard["zebra"]
    params: RotationInternalParameters = setup_and_run_rotation_plan_for_tests_standard[
        "test_rotation_params"
    ]
    expt_params = params.experiment_params

    assert zebra.pc.gate_start.get() == expt_params.omega_start
    assert zebra.pc.gate_start.get() == expt_params.omega_start
    assert zebra.pc.pulse_start.get() == expt_params.shutter_opening_time_s


def test_full_rotation_plan_smargon_settings(
    run_full_rotation_plan,
    test_rotation_params,
):
    smargon: Smargon = run_full_rotation_plan.smargon
    params: RotationInternalParameters = test_rotation_params
    expt_params = params.experiment_params

    omega_set: MagicMock = smargon.omega.set
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
):
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
    RE,
    test_rotation_params,
    smargon: Smargon,
    zebra: Zebra,
    eiger: EigerDetector,
    detector_motion: DetectorMotion,
    backlight: Backlight,
    attenuator: Attenuator,
    mock_rotation_subscriptions: RotationCallbackCollection,
):
    class MyTestException(Exception):
        pass

    eiger.stage = MagicMock()
    eiger.unstage = MagicMock()
    smargon.omega.set = MagicMock(
        side_effect=MyTestException("Experiment fails because this is a test")
    )

    composite = RotationScanComposite(
        attenuator=attenuator,
        backlight=backlight,
        detector_motion=detector_motion,
        eiger=eiger,
        flux=MagicMock(),
        smargon=smargon,
        undulator=MagicMock(),
        synchrotron=MagicMock(),
        s4_slit_gaps=MagicMock(),
        zebra=zebra,
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
    with patch(
        "hyperion.experiment_plans.rotation_scan_plan.RotationCallbackCollection.from_params",
        lambda _: mock_rotation_subscriptions,
    ):
        with pytest.raises(MyTestException) as exc:
            RE(
                rotation_scan(
                    composite,
                    test_rotation_params,
                )
            )
        assert "Experiment fails because this is a test" in exc.value.args[0]
        cleanup_plan.assert_called_once()


@pytest.mark.s03
@patch("bluesky.plan_stubs.wait")
@patch("hyperion.external_interaction.callbacks.rotation.nexus_callback.NexusWriter")
@patch(
    "hyperion.external_interaction.callbacks.rotation.callback_collection.RotationZocaloCallback"
)
def test_ispyb_deposition_in_plan(
    bps_wait,
    nexus_writer,
    zocalo_callback,
    fake_create_rotation_devices,
    RE,
    test_rotation_params: RotationInternalParameters,
    fetch_comment,
    fetch_datacollection_attribute,
    undulator,
    attenuator,
    synchrotron,
    s4_slit_gaps,
    flux,
):
    test_wl = 0.71
    test_bs_x = 0.023
    test_bs_y = 0.047
    test_exp_time = 0.023
    test_img_wid = 0.27

    test_rotation_params.experiment_params.image_width = test_img_wid
    test_rotation_params.hyperion_params.ispyb_params.beam_size_x = test_bs_x
    test_rotation_params.hyperion_params.ispyb_params.beam_size_y = test_bs_y
    test_rotation_params.hyperion_params.detector_params.exposure_time = test_exp_time
    test_rotation_params.hyperion_params.ispyb_params.current_energy_ev = (
        convert_angstrom_to_eV(test_wl)
    )
    callbacks = RotationCallbackCollection.from_params(test_rotation_params)
    callbacks.ispyb_handler.ispyb.ISPYB_CONFIG_PATH = DEV_ISPYB_DATABASE_CFG

    composite = RotationScanComposite(
        attenuator=attenuator,
        backlight=MagicMock(),
        detector_motion=MagicMock(),
        eiger=MagicMock(),
        flux=flux,
        smargon=MagicMock(),
        undulator=undulator,
        synchrotron=synchrotron,
        s4_slit_gaps=s4_slit_gaps,
        zebra=MagicMock(),
    )

    with (
        patch(
            "bluesky.preprocessors.__read_and_stash_a_motor",
            fake_read,
        ),
        patch(
            "hyperion.experiment_plans.rotation_scan_plan.RotationCallbackCollection.from_params",
            lambda _: callbacks,
        ),
    ):
        RE(
            rotation_scan(
                composite,
                test_rotation_params,
            )
        )

    dcid = callbacks.ispyb_handler.ispyb_ids[0]
    comment = fetch_comment(dcid)
    assert comment == "Hyperion rotation scan"
    wavelength = fetch_datacollection_attribute(dcid, "wavelength")
    beamsize_x = fetch_datacollection_attribute(dcid, "beamSizeAtSampleX")
    beamsize_y = fetch_datacollection_attribute(dcid, "beamSizeAtSampleY")
    exposure = fetch_datacollection_attribute(dcid, "exposureTime")

    assert wavelength == test_wl
    assert beamsize_x == test_bs_x
    assert beamsize_y == test_bs_y
    assert exposure == test_exp_time


@patch(
    "hyperion.experiment_plans.rotation_scan_plan.move_to_start_w_buffer", autospec=True
)
def test_acceleration_offset_calculated_correctly(
    mock_move_to_start: MagicMock,
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
    smargon.omega.acceleration.sim_put(0.2)
    setup_and_run_rotation_plan_for_tests(
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

    expected_start_angle = (
        test_rotation_params.hyperion_params.detector_params.omega_start
    )

    mock_move_to_start.assert_called_once_with(
        smargon.omega, expected_start_angle, pytest.approx(0.3)
    )
