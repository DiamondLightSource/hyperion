from unittest.mock import MagicMock, patch

from ophyd.sim import make_fake_device

import artemis.device_setup_plans.setup_zebra_for_fgs as szffgs
from artemis.devices.zebra import (  # DISCONNECT,; IN4_TTL,; OR1,; PC_PULSE,; TTL_SHUTTER,; TTL_XSPRESS3,
    IN3_TTL,
    TTL_DETECTOR,
    Zebra,
)


@patch("bps.abs_set")
def setup_zebra_for_fgs(abs_set: MagicMock):
    zebra: Zebra = make_fake_device(Zebra)
    szffgs.set_zebra_shutter_to_manual(zebra)
    MagicMock.assert_called_with(zebra.output.out_pvs[TTL_DETECTOR], IN3_TTL)
