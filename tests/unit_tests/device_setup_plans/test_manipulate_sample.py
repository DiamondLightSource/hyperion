from unittest.mock import MagicMock, patch

from bluesky.run_engine import RunEngine
from dodal.devices.aperturescatterguard import (
    AperturePositionGDANames,
    ApertureScatterguard,
)

from hyperion.device_setup_plans.manipulate_sample import move_aperture_if_required


@patch("bluesky.plan_stubs.abs_set")
async def test_move_aperture_goes_to_correct_position(
    mock_set: MagicMock, aperture_scatterguard: ApertureScatterguard, RE: RunEngine
):
    assert aperture_scatterguard.aperture_positions

    RE(
        move_aperture_if_required(
            aperture_scatterguard, AperturePositionGDANames.LARGE_APERTURE
        )
    )
    mock_set.assert_called_once_with(
        aperture_scatterguard,
        aperture_scatterguard.aperture_positions.LARGE,
        group="move_aperture",
    )


async def test_move_aperture_does_nothing_when_none_selected(
    aperture_scatterguard: ApertureScatterguard, RE: RunEngine
):
    assert aperture_scatterguard.aperture_positions
    with patch("bluesky.plan_stubs.abs_set") as mock_set:
        RE(move_aperture_if_required(aperture_scatterguard, None))
        mock_set.assert_not_called()
