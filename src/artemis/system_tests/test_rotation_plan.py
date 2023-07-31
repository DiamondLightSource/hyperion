from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import DEFAULT, MagicMock, patch

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

from artemis.experiment_plans.rotation_scan_plan import (
    DEFAULT_DIRECTION,
    create_devices,
    move_to_end_w_buffer,
    move_to_start_w_buffer,
    rotation_scan_plan,
)
from artemis.experiment_plans.tests.conftest import fake_read
from artemis.external_interaction.callbacks.rotation.rotation_callback_collection import (
    RotationCallbackCollection,
)
from artemis.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)

if TYPE_CHECKING:
    from dodal.devices.backlight import Backlight  # noqa
    from dodal.devices.detector_motion import DetectorMotion  # noqa
    from dodal.devices.eiger import EigerDetector  # noqa
    from dodal.devices.smargon import Smargon
    from dodal.devices.zebra import Zebra  # noqa


@pytest.fixture()
def devices():
    with patch("artemis.experiment_plans.rotation_scan_plan.i03.backlight"), patch(
        "artemis.experiment_plans.rotation_scan_plan.i03.detector_motion"
    ):
        return create_devices()


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


TEST_OFFSET = 1
TEST_SHUTTER_DEGREES = 2


@pytest.mark.s03()
def test_move_to_start(devices, RE):
    # may need to run 'caput BL03S-MO-SGON-01:OMEGA.VMAX 120' as S03 has 45 by default
    smargon: Smargon = devices["smargon"]
    start_angle = 153
    RE(
        move_to_start_w_buffer(
            smargon.omega, start_angle, TEST_OFFSET, wait_for_velocity_set=False
        )
    )
    velocity = smargon.omega.velocity.get()
    omega_position = smargon.omega.user_setpoint.get()

    assert velocity == 120
    assert omega_position == (start_angle - TEST_OFFSET * DEFAULT_DIRECTION)


@pytest.mark.s03()
def test_move_to_end(devices, RE):
    smargon: Smargon = devices["smargon"]
    scan_width = 153
    RE(move_to_end_w_buffer(smargon.omega, scan_width, TEST_OFFSET))
    omega_position = smargon.omega.user_setpoint.get()

    assert omega_position == (
        (scan_width + TEST_OFFSET * 2 + TEST_SHUTTER_DEGREES) * DEFAULT_DIRECTION
    )
