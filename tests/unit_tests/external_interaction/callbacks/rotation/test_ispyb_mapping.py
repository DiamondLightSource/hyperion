from unittest.mock import patch

from hyperion.external_interaction.callbacks.rotation.ispyb_mapping import (
    populate_data_collection_info_for_rotation,
)


def test_populate_data_collection_info_for_rotation_checks_snapshots(
    dummy_rotation_params,
):
    with patch("hyperion.log.ISPYB_LOGGER.warning", autospec=True) as warning:
        dummy_rotation_params.ispyb_extras.xtal_snapshots_omega_start = None
        populate_data_collection_info_for_rotation(dummy_rotation_params)
        warning.assert_called_once_with("No xtal snapshot paths sent to ISPyB!")
