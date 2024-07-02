import numpy as np
from bluesky import plan_stubs as bps
from dodal.devices.smargon import Smargon

from hyperion.exceptions import WarningException


def move_smargon_warn_on_out_of_range(
    smargon: Smargon, position: np.ndarray | list[float] | tuple[float, float, float]
):
    """Throws a WarningException if the specified position is out of range for the
    smargon. Otherwise moves to that position."""
    limits = yield from smargon.get_xyz_limits()
    if not limits.position_valid(position):
        raise WarningException(
            "Pin tip centring failed - pin too long/short/bent and out of range"
        )
    yield from bps.mv(
        smargon.x,
        position[0],
        smargon.y,
        position[1],
        smargon.z,
        position[2],
    )
