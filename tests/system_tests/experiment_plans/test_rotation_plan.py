from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from dodal.beamlines import i03

from hyperion.experiment_plans.rotation_scan_plan import (
    DEFAULT_DIRECTION,
    RotationScanComposite,
    move_to_end_w_buffer,
    move_to_start_w_buffer,
)

if TYPE_CHECKING:
    from dodal.devices.backlight import Backlight  # noqa
    from dodal.devices.detector.detector_motion import DetectorMotion  # noqa
    from dodal.devices.eiger import EigerDetector  # noqa
    from dodal.devices.smargon import Smargon
    from dodal.devices.zebra import Zebra  # noqa


@pytest.fixture()
def devices():
    return RotationScanComposite(
        attenuator=i03.attenuator(),
        backlight=i03.backlight(),
        dcm=i03.dcm(fake_with_ophyd_sim=True),
        detector_motion=i03.detector_motion(fake_with_ophyd_sim=True),
        eiger=i03.eiger(),
        flux=i03.flux(fake_with_ophyd_sim=True),
        smargon=i03.smargon(),
        undulator=i03.undulator(),
        synchrotron=i03.synchrotron(fake_with_ophyd_sim=True),
        s4_slit_gaps=i03.s4_slit_gaps(),
        zebra=i03.zebra(),
        robot=i03.robot(fake_with_ophyd_sim=True),
    )


TEST_OFFSET = 1
TEST_SHUTTER_DEGREES = 2


@pytest.mark.s03()
def test_move_to_start(devices, RE):
    # may need to run 'caput BL03S-MO-SGON-01:OMEGA.VMAX 120' as S03 has 45 by default
    smargon: Smargon = devices.smargon
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
    smargon: Smargon = devices.smargon
    scan_width = 153
    RE(
        move_to_end_w_buffer(
            smargon.omega, scan_width, TEST_OFFSET, TEST_SHUTTER_DEGREES
        )
    )
    omega_position = smargon.omega.user_setpoint.get()

    assert omega_position == (
        (scan_width + TEST_OFFSET * 2 + TEST_SHUTTER_DEGREES) * DEFAULT_DIRECTION
    )
