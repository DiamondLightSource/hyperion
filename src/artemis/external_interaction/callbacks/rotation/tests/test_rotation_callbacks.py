from unittest.mock import MagicMock, patch

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import pytest
from bluesky.run_engine import RunEngine

from artemis.external_interaction.callbacks.rotation.nexus_callback import (
    RotationNexusFileHandlerCallback,
)
from artemis.external_interaction.callbacks.rotation.rotation_callback_collection import (
    RotationCallbackCollection,
)
from artemis.parameters.external_parameters import from_file
from artemis.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)


@pytest.fixture
def params():
    return RotationInternalParameters(
        **from_file(
            "src/artemis/parameters/tests/test_data/good_test_rotation_scan_parameters.json"
        )
    )


def test_callback_collection_init(params):
    callbacks = RotationCallbackCollection()
    assert isinstance(callbacks.nexus_handler, RotationNexusFileHandlerCallback)


def fake_get_plan(
    parameters: RotationInternalParameters, subscriptions: RotationCallbackCollection
):
    @bpp.subs_decorator(list(subscriptions))
    @bpp.set_run_key_decorator("run_gridscan_move_and_tidy")
    @bpp.run_decorator(  # attach experiment metadata to the start document
        md={
            "subplan_name": "rotation_scan_with_cleanup",
            "hyperion_internal_parameters": parameters.json(),
        }
    )
    def plan():
        yield from bps.sleep(0)

    return plan()


def test_nexus_handler_gets_documents_in_mock_plan(params: RotationInternalParameters):
    RE = RunEngine({})

    cb = RotationCallbackCollection.from_params(params)
    cb.nexus_handler.start = MagicMock()
    cb.nexus_handler.stop = MagicMock()

    RE(fake_get_plan(params, cb))

    cb.nexus_handler.start.assert_called_once()
    call_content = cb.nexus_handler.start.call_args[0][0]
    assert call_content["hyperion_internal_parameters"] == params.json()
    cb.nexus_handler.stop.assert_called_once()
