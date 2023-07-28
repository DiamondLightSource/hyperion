from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from bluesky.utils import Msg
from dodal.beamlines import i03
from ophyd.status import Status

from artemis.experiment_plans.rotation_scan_plan import (
    DIRECTION,
    get_plan,
    move_to_end_w_buffer,
    move_to_start_w_buffer,
    rotation_scan_plan,
)
from artemis.external_interaction.callbacks.rotation.rotation_callback_collection import (
    RotationCallbackCollection,
)
from artemis.external_interaction.system_tests.conftest import (  # noqa
    fetch_comment,
    fetch_datacollection_attribute,
)
from artemis.parameters.constants import DEV_ISPYB_DATABASE_CFG
from artemis.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)

if TYPE_CHECKING:
    from dodal.devices.attenuator import Attenuator
    from dodal.devices.backlight import Backlight
    from dodal.devices.detector_motion import DetectorMotion
    from dodal.devices.eiger import EigerDetector
    from dodal.devices.smargon import Smargon
    from dodal.devices.zebra import Zebra

TEST_OFFSET = 1
TEST_SHUTTER_OPENING_DEGREES = 2.5


def test_move_to_start(smargon: Smargon, RE):
    start_angle = 153
    mock_velocity_set = MagicMock(return_value=Status(done=True, success=True))
    with patch.object(smargon.omega.velocity, "set", mock_velocity_set):
        RE(move_to_start_w_buffer(smargon.omega, start_angle, TEST_OFFSET))

    mock_velocity_set.assert_called_with(120)
    assert smargon.omega.user_readback.get() == start_angle - TEST_OFFSET * DIRECTION


def __fake_read(obj, initial_positions, _):
    initial_positions[obj] = 0
    yield Msg("null", obj)


def test_move_to_end(smargon: Smargon, RE):
    scan_width = 153
    with patch(
        "bluesky.preprocessors.__read_and_stash_a_motor",
        __fake_read,
    ):
        RE(
            move_to_end_w_buffer(
                smargon.omega, scan_width, TEST_OFFSET, TEST_SHUTTER_OPENING_DEGREES
            )
        )

    distance_to_move = (
        scan_width + TEST_SHUTTER_OPENING_DEGREES + TEST_OFFSET * 2 + 0.1
    ) * DIRECTION

    assert smargon.omega.user_readback.get() == distance_to_move


@patch("dodal.beamlines.beamline_utils.active_device_is_same_type", lambda a, b: True)
@patch("artemis.experiment_plans.rotation_scan_plan.rotation_scan_plan", autospec=True)
def test_get_plan(
    plan: MagicMock,
    RE,
    test_rotation_params,
    smargon: Smargon,
    zebra: Zebra,
    eiger: EigerDetector,
    detector_motion: DetectorMotion,
    backlight: Backlight,
    mock_rotation_subscriptions: RotationCallbackCollection,
):
    eiger.stage = MagicMock()
    eiger.unstage = MagicMock()
    zebra.pc.arm.armed.set(False)
    with (
        patch("dodal.beamlines.i03.smargon", return_value=smargon),
        patch("dodal.beamlines.i03.eiger", return_value=eiger),
        patch("dodal.beamlines.i03.zebra", return_value=zebra),
        patch("dodal.beamlines.i03.backlight", return_value=backlight),
        patch(
            "artemis.experiment_plans.rotation_scan_plan.DetectorMotion",
            return_value=detector_motion,
        ),
        patch(
            "artemis.experiment_plans.rotation_scan_plan.RotationCallbackCollection.from_params",
            lambda _: mock_rotation_subscriptions,
        ),
    ):
        RE(get_plan(test_rotation_params))

    eiger.stage.assert_called()
    eiger.unstage.assert_called()


@patch("bluesky.plan_stubs.wait", autospec=True)
def test_rotation_plan(
    bps_wait: MagicMock,
    RE,
    test_rotation_params,
    smargon: Smargon,
    zebra: Zebra,
    eiger: EigerDetector,
    attenuator: Attenuator,
    detector_motion: DetectorMotion,
    backlight: Backlight,
    mock_rotation_subscriptions: RotationCallbackCollection,
    synchrotron,
    s4_slit_gaps,
    undulator,
    flux,
):
    mock_omega_sets = MagicMock(return_value=Status(done=True, success=True))

    mock_arm = MagicMock(
        side_effect=zebra.pc.arm.armed.set, return_value=Status(done=True, success=True)
    )
    zebra.pc.arm.arm_set.set = mock_arm

    smargon.omega.velocity.set = mock_omega_sets
    smargon.omega.set = mock_omega_sets

    with (
        patch(
            "bluesky.preprocessors.__read_and_stash_a_motor",
            __fake_read,
        ),
        patch(
            "artemis.experiment_plans.rotation_scan_plan.RotationCallbackCollection.from_params",
            lambda _: mock_rotation_subscriptions,
        ),
        patch("dodal.beamlines.i03.undulator", lambda: undulator),
        patch("dodal.beamlines.i03.synchrotron", lambda: synchrotron),
        patch("dodal.beamlines.i03.s4_slit_gaps", lambda: s4_slit_gaps),
        patch("dodal.beamlines.i03.flux", lambda: flux),
        patch("dodal.beamlines.i03.attenuator", lambda: attenuator),
    ):
        RE(
            rotation_scan_plan(
                test_rotation_params,
                eiger,
                smargon,
                zebra,
                backlight,
                attenuator,
                detector_motion,
            )
        )
    # once for each velocity set and once for each position set for a total of 4 calls
    assert mock_omega_sets.call_count == 4


@patch("artemis.experiment_plans.rotation_scan_plan.cleanup_plan", autospec=True)
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
    eiger.stage = MagicMock()
    eiger.unstage = MagicMock()
    smargon.omega.set = MagicMock(
        side_effect=Exception("Experiment fails because this is a test")
    )

    # check main subplan part fails
    with pytest.raises(Exception):
        RE(
            rotation_scan_plan(
                test_rotation_params, eiger, smargon, zebra, backlight, detector_motion
            )
        )
        cleanup_plan.assert_not_called()
    # check that failure is handled in composite plan
    with (
        patch("dodal.beamlines.i03.smargon", return_value=smargon),
        patch("dodal.beamlines.i03.eiger", return_value=eiger),
        patch("dodal.beamlines.i03.zebra", return_value=zebra),
        patch("dodal.beamlines.i03.backlight", return_value=backlight),
        patch("dodal.beamlines.i03.detector_motion", return_value=detector_motion),
        patch("dodal.beamlines.i03.attenuator", return_value=attenuator),
        patch(
            "artemis.experiment_plans.rotation_scan_plan.RotationCallbackCollection.from_params",
            lambda _: mock_rotation_subscriptions,
        ),
    ):
        with pytest.raises(Exception) as exc:
            RE(
                get_plan(
                    test_rotation_params,
                )
            )
        assert "Experiment fails because this is a test" in exc.value.args[0]
        cleanup_plan.assert_called_once()


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


@pytest.mark.s03
@patch("bluesky.plan_stubs.wait")
@patch("artemis.external_interaction.nexus.write_nexus.NexusWriter")
def test_ispyb_deposition_in_plan(
    bps_wait,
    nexus_writer,
    fake_create_devices,
    RE,
    test_rotation_params: RotationInternalParameters,
    fetch_comment,
    fetch_datacollection_attribute,
    undulator,
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
    test_rotation_params.artemis_params.ispyb_params.beam_size_x = test_bs_x
    test_rotation_params.artemis_params.ispyb_params.beam_size_y = test_bs_y
    test_rotation_params.artemis_params.detector_params.exposure_time = test_exp_time
    test_rotation_params.artemis_params.ispyb_params.wavelength = test_wl
    callbacks = RotationCallbackCollection.from_params(test_rotation_params)
    callbacks.ispyb_handler.ispyb.ISPYB_CONFIG_PATH = DEV_ISPYB_DATABASE_CFG

    with (
        patch(
            "artemis.experiment_plans.rotation_scan_plan.create_devices",
            lambda: fake_create_devices,
        ),
        patch("dodal.beamlines.i03.undulator", return_value=undulator),
        patch("dodal.beamlines.i03.synchrotron", return_value=synchrotron),
        patch("dodal.beamlines.i03.s4_slit_gaps", return_value=s4_slit_gaps),
        patch("dodal.beamlines.i03.flux", return_value=flux),
        patch(
            "bluesky.preprocessors.__read_and_stash_a_motor",
            __fake_read,
        ),
        patch(
            "artemis.experiment_plans.rotation_scan_plan.RotationCallbackCollection.from_params",
            lambda _: callbacks,
        ),
    ):
        RE(
            get_plan(
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
