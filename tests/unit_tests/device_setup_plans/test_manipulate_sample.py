from unittest.mock import patch

from bluesky.run_engine import RunEngine
from dodal.devices.aperturescatterguard import (
    ApertureInOut,
    AperturePosition,
    AperturePositionGDANames,
    ApertureScatterguard,
)

from hyperion.device_setup_plans.manipulate_sample import move_aperture_if_required


async def test_move_aperture_goes_to_correct_position(
    aperture_scatterguard: ApertureScatterguard, RE: RunEngine
):
    with patch.object(aperture_scatterguard, "set") as mock_set:
        RE(
            move_aperture_if_required(
                aperture_scatterguard, AperturePositionGDANames.LARGE_APERTURE
            )
        )
        mock_set.assert_called_once_with((ApertureInOut.IN, AperturePosition.LARGE))


async def test_move_aperture_does_nothing_when_none_selected(
    aperture_scatterguard: ApertureScatterguard, RE: RunEngine
):
    with patch.object(aperture_scatterguard, "set") as mock_set:
        RE(move_aperture_if_required(aperture_scatterguard, None))
        mock_set.assert_not_called()
