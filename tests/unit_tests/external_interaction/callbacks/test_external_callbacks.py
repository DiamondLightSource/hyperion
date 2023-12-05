from unittest.mock import MagicMock, patch

import pytest

from hyperion.external_interaction.callbacks.__main__ import (
    main,
    setup_callbacks,
    setup_logging,
    setup_threads,
)
from hyperion.log import ISPYB_LOGGER, NEXUS_LOGGER


@patch("hyperion.external_interaction.callbacks.__main__.setup_callbacks")
@patch("hyperion.external_interaction.callbacks.__main__.setup_logging")
@patch("hyperion.external_interaction.callbacks.__main__.setup_threads")
def test_main_function(
    setup_threads: MagicMock, setup_logging: MagicMock, setup_callbacks: MagicMock
):
    setup_threads.return_value = (MagicMock(), MagicMock(), MagicMock(), MagicMock())
    main()
    setup_threads.assert_called()
    setup_logging.assert_called()
    setup_callbacks.assert_called()


def test_setup_callbacks():
    current_number_of_callbacks = 6
    cbs = setup_callbacks()
    assert len(cbs) == current_number_of_callbacks
    assert len(set(cbs)) == current_number_of_callbacks


@pytest.mark.skip_log_setup
@patch(
    "hyperion.external_interaction.callbacks.__main__.parse_cli_args",
    return_value=("DEBUG", None, True, None),
)
def test_setup_logging(parse_cli_args):
    assert len(ISPYB_LOGGER.handlers) == 0
    assert len(NEXUS_LOGGER.handlers) == 0
    setup_logging()
    assert len(ISPYB_LOGGER.handlers) == 3
    assert len(NEXUS_LOGGER.handlers) == 3
