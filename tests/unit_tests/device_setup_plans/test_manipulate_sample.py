from unittest.mock import patch

import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.aperturescatterguard import (
    AperturePosition,
    AperturePositionGDANames,
    ApertureScatterguard,
)

from hyperion.device_setup_plans.manipulate_sample import move_aperture_if_required


@pytest.mark.parametrize(
    "gda_position, set_position",
    [
        (AperturePositionGDANames.SMALL_APERTURE, AperturePosition.SMALL),
        (AperturePositionGDANames.MEDIUM_APERTURE, AperturePosition.MEDIUM),
        (AperturePositionGDANames.ROBOT_LOAD, AperturePosition.ROBOT_LOAD),
        (AperturePositionGDANames.LARGE_APERTURE, AperturePosition.LARGE),
    ],
)
async def test_move_aperture_goes_to_correct_position(
    aperture_scatterguard: ApertureScatterguard,
    RE: RunEngine,
    gda_position,
    set_position,
):
    with patch.object(aperture_scatterguard, "set") as mock_set:
        RE(move_aperture_if_required(aperture_scatterguard, gda_position))
        mock_set.assert_called_once_with(
            set_position,
        )


async def test_move_aperture_does_nothing_when_none_selected(
    aperture_scatterguard: ApertureScatterguard, RE: RunEngine
):
    with patch.object(aperture_scatterguard, "set") as mock_set:
        RE(move_aperture_if_required(aperture_scatterguard, None))
        mock_set.assert_not_called()
