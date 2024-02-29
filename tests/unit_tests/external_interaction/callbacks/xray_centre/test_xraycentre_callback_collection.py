from unittest.mock import MagicMock

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from bluesky.run_engine import RunEngine

from hyperion.external_interaction.callbacks.xray_centre.callback_collection import (
    XrayCentreCallbackCollection,
)


def test_callback_collection_init():
    callbacks = XrayCentreCallbackCollection()
    assert len(list(callbacks)) == 3


def test_callback_collection_list():
    callbacks = XrayCentreCallbackCollection()
    callback_list = list(callbacks)
    assert len(callback_list) == 3
    assert callbacks.ispyb_handler in callback_list
    assert callbacks.nexus_handler in callback_list
    assert callbacks.zocalo_handler in callback_list


def test_subscribe_in_plan():
    callbacks = XrayCentreCallbackCollection()
    document_event_mock = MagicMock()
    callbacks.ispyb_handler.start = document_event_mock
    callbacks.ispyb_handler.activity_gated_stop = document_event_mock
    callbacks.zocalo_handler.activity_gated_start = document_event_mock
    callbacks.zocalo_handler.activity_gated_stop = document_event_mock
    callbacks.nexus_handler.activity_gated_start = document_event_mock
    callbacks.nexus_handler.stop = document_event_mock

    RE = RunEngine()

    @bpp.subs_decorator(callbacks.ispyb_handler)
    def outer_plan():
        @bpp.set_run_key_decorator("inner_plan")
        @bpp.run_decorator(md={"subplan_name": "inner_plan"})
        def inner_plan():
            yield from bps.sleep(0)

        yield from inner_plan()

    RE(outer_plan())

    document_event_mock.assert_called()
