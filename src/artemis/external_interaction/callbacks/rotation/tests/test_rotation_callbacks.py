from unittest.mock import MagicMock, patch

import bluesky.plan_stubs as bps
import pytest
from bluesky.run_engine import RunEngine

from artemis.external_interaction.callbacks.rotation.nexus_callback import (
    RotationNexusFileHandlerCallback,
)
from artemis.external_interaction.callbacks.rotation.rotation_callback_collection import (
    RotationCallbackCollection,
)
from artemis.parameters.external_parameters import from_file
from artemis.parameters.internal_parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)


@pytest.fixture
def params():
    return RotationInternalParameters.from_external_dict(
        from_file(
            "src/artemis/parameters/tests/test_data/good_test_rotation_scan_parameters.json"
        )
    )


def test_callback_collection_init(params):
    callbacks = RotationCallbackCollection.from_params(params)
    assert isinstance(callbacks.nexus_handler, RotationNexusFileHandlerCallback)
    assert callbacks.nexus_handler.params == params


def test_nexus_handler(params):
    RE = RunEngine({})

    def plan():
        yield from bps.open_run()
        yield from bps.close_run()

    cb = RotationCallbackCollection.from_params(params).nexus_handler
    logger_mock = MagicMock()

    RE.subscribe(cb)

    with patch(
        "artemis.external_interaction.callbacks.rotation.nexus_callback.LOGGER.info",
        logger_mock,
    ):
        RE(plan())

    assert logger_mock.call_count == 2
