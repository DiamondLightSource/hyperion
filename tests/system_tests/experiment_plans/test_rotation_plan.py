from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from dodal.beamlines import i03

from hyperion.experiment_plans.rotation_scan_plan import (
    RotationScanComposite,
)

if TYPE_CHECKING:
    from dodal.devices.backlight import Backlight  # noqa
    from dodal.devices.detector_motion import DetectorMotion  # noqa
    from dodal.devices.eiger import EigerDetector  # noqa
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
