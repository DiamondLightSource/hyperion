from typing import Any, Callable
from unittest.mock import MagicMock

import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
import pytest
from bluesky.run_engine import RunEngine
from event_model import DocumentNames
from event_model.documents.event import Event
from event_model.documents.event_descriptor import EventDescriptor
from event_model.documents.run_start import RunStart
from event_model.documents.run_stop import RunStop
from ophyd.sim import SynAxis

from hyperion.external_interaction.callbacks.plan_reactive_callback import (
    PlanReactiveCallback,
)


class TestCallback(PlanReactiveCallback):
    def __init__(self, *, emit: Callable[..., Any] | None = None) -> None:
        super().__init__(emit=emit)
        self.activity_gated_start = MagicMock()
        self.activity_gated_descriptor = MagicMock()
        self.activity_gated_event = MagicMock()
        self.activity_gated_stop = MagicMock()


@pytest.fixture
def mocked_test_callback():
    t = TestCallback()
    return t


@pytest.fixture
def RE_with_mock_callback(mocked_test_callback):
    RE = RunEngine()
    RE.subscribe(mocked_test_callback)
    yield RE, mocked_test_callback


def get_test_plan(callback_name):
    s = SynAxis(name="fake_signal")

    @bpp.run_decorator(md={"activate_callbacks": [callback_name]})
    def test_plan():
        yield from bps.create()
        yield from bps.read(s)
        yield from bps.save()

    return test_plan, s


def test_activity_gated_functions_not_called_when_inactive(
    mocked_test_callback: TestCallback,
):
    mocked_test_callback.start({})  # type: ignore
    mocked_test_callback.activity_gated_start.assert_not_called()  # type: ignore
    mocked_test_callback.descriptor({})  # type: ignore
    mocked_test_callback.activity_gated_descriptor.assert_not_called()  # type: ignore
    mocked_test_callback.event({})  # type: ignore
    mocked_test_callback.activity_gated_event.assert_not_called()  # type: ignore
    mocked_test_callback.stop({})  # type: ignore
    mocked_test_callback.activity_gated_stop.assert_not_called()  # type: ignore


def test_activity_gated_functions_called_when_active(
    mocked_test_callback: TestCallback,
):
    mocked_test_callback.active = True
    mocked_test_callback.start({})  # type: ignore
    mocked_test_callback.activity_gated_start.assert_called_once()  # type: ignore
    mocked_test_callback.descriptor({})  # type: ignore
    mocked_test_callback.activity_gated_descriptor.assert_called_once()  # type: ignore
    mocked_test_callback.event({})  # type: ignore
    mocked_test_callback.activity_gated_event.assert_called_once()  # type: ignore
    mocked_test_callback.stop({})  # type: ignore
    mocked_test_callback.activity_gated_stop.assert_called_once()  # type: ignore


def test_activates_on_appropriate_start_doc(mocked_test_callback):
    assert mocked_test_callback.active is False
    mocked_test_callback.start({"activate_callbacks": ["TestCallback"]})
    assert mocked_test_callback.active is True


def test_deactivates_on_inappropriate_start_doc(mocked_test_callback):
    assert mocked_test_callback.active is False
    mocked_test_callback.start({"activate_callbacks": ["TestCallback"]})
    assert mocked_test_callback.active is True
    mocked_test_callback.start({"activate_callbacks": ["TestNotCallback"]})
    assert mocked_test_callback.active is False


def test_deactivates_on_appropriate_stop_doc_uid(mocked_test_callback):
    assert mocked_test_callback.active is False
    mocked_test_callback.start({"activate_callbacks": ["TestCallback"], "uid": "foo"})
    assert mocked_test_callback.active is True
    mocked_test_callback.stop({"run_start": "foo"})
    assert mocked_test_callback.active is False


def test_doesnt_deactivate_on_inappropriate_stop_doc_uid(mocked_test_callback):
    assert mocked_test_callback.active is False
    mocked_test_callback.start({"activate_callbacks": ["TestCallback"], "uid": "foo"})
    assert mocked_test_callback.active is True
    mocked_test_callback.stop({"run_start": "bar"})
    assert mocked_test_callback.active is True


def test_activates_on_metadata(RE_with_mock_callback: tuple[RunEngine, TestCallback]):
    RE, callback = RE_with_mock_callback
    RE(get_test_plan("TestCallback")[0]())
    callback.activity_gated_start.assert_called_once()
    callback.activity_gated_descriptor.assert_called_once()
    callback.activity_gated_event.assert_called_once()
    callback.activity_gated_stop.assert_called_once()


def test_deactivates_after_closing(
    RE_with_mock_callback: tuple[RunEngine, TestCallback]
):
    RE, callback = RE_with_mock_callback
    assert callback.active is False
    RE(get_test_plan("TestCallback")[0]())
    assert callback.active is False


def test_doesnt_activate_on_wrong_metadata(
    RE_with_mock_callback: tuple[RunEngine, TestCallback]
):
    RE, callback = RE_with_mock_callback
    RE(get_test_plan("TestNotCallback")[0]())
    callback.activity_gated_start.assert_not_called()  # type: ignore
    callback.activity_gated_descriptor.assert_not_called()  # type: ignore
    callback.activity_gated_event.assert_not_called()  # type: ignore
    callback.activity_gated_stop.assert_not_called()  # type: ignore
