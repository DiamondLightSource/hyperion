from unittest.mock import MagicMock

import pytest
from bluesky.run_engine import RunEngine
from event_model.documents import Event, EventDescriptor, RunStart, RunStop

from hyperion.external_interaction.callbacks.plan_reactive_callback import (
    PlanReactiveCallback,
)

from ..conftest import MockReactiveCallback, get_test_plan


def test_activity_gated_functions_not_called_when_inactive(
    mocked_test_callback: MockReactiveCallback,
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
    mocked_test_callback: MockReactiveCallback,
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
    mocked_test_callback.start({"activate_callbacks": ["MockReactiveCallback"]})
    assert mocked_test_callback.active is True


def test_deactivates_on_inappropriate_start_doc(mocked_test_callback):
    assert mocked_test_callback.active is False
    mocked_test_callback.start({"activate_callbacks": ["MockReactiveCallback"]})
    assert mocked_test_callback.active is True
    mocked_test_callback.start({"activate_callbacks": ["TestNotCallback"]})
    assert mocked_test_callback.active is False


def test_deactivates_on_appropriate_stop_doc_uid(mocked_test_callback):
    assert mocked_test_callback.active is False
    mocked_test_callback.start(
        {"activate_callbacks": ["MockReactiveCallback"], "uid": "foo"}
    )
    assert mocked_test_callback.active is True
    mocked_test_callback.stop({"run_start": "foo"})
    assert mocked_test_callback.active is False


def test_doesnt_deactivate_on_inappropriate_stop_doc_uid(mocked_test_callback):
    assert mocked_test_callback.active is False
    mocked_test_callback.start(
        {"activate_callbacks": ["MockReactiveCallback"], "uid": "foo"}
    )
    assert mocked_test_callback.active is True
    mocked_test_callback.stop({"run_start": "bar"})
    assert mocked_test_callback.active is True


def test_activates_on_metadata(
    RE_with_mock_callback: tuple[RunEngine, MockReactiveCallback]
):
    RE, callback = RE_with_mock_callback
    RE(get_test_plan("MockReactiveCallback")[0]())
    callback.activity_gated_start.assert_called_once()
    callback.activity_gated_descriptor.assert_called_once()
    callback.activity_gated_event.assert_called_once()
    callback.activity_gated_stop.assert_called_once()


def test_deactivates_after_closing(
    RE_with_mock_callback: tuple[RunEngine, MockReactiveCallback]
):
    RE, callback = RE_with_mock_callback
    assert callback.active is False
    RE(get_test_plan("MockReactiveCallback")[0]())
    assert callback.active is False


def test_doesnt_activate_on_wrong_metadata(
    RE_with_mock_callback: tuple[RunEngine, MockReactiveCallback]
):
    RE, callback = RE_with_mock_callback
    RE(get_test_plan("TestNotCallback")[0]())
    callback.activity_gated_start.assert_not_called()  # type: ignore
    callback.activity_gated_descriptor.assert_not_called()  # type: ignore
    callback.activity_gated_event.assert_not_called()  # type: ignore
    callback.activity_gated_stop.assert_not_called()  # type: ignore


def test_cb_logs_and_raises_exception():
    cb = MockReactiveCallback()
    cb.active = True

    class MockTestException(Exception): ...

    e = MockTestException()

    def mock_excepting_func(_):
        raise e

    cb.log = MagicMock()

    with pytest.raises(MockTestException):
        cb._run_activity_gated("start", mock_excepting_func, {"start": "test"})

    cb.log.exception.assert_called_with(e)


def test_emit_called_correctly():
    receiving_cb = MockReactiveCallback()
    test_cb = PlanReactiveCallback(emit=receiving_cb, log=MagicMock())

    start_doc: RunStart = {"uid": "123", "time": 0}
    desc_doc: EventDescriptor = {
        "data_keys": {},
        "run_start": "123",
        "uid": "987",
        "time": 0,
    }
    event_doc: Event = {
        "data": {},
        "time": 0,
        "descriptor": "987",
        "timestamps": {},
        "uid": "999",
        "seq_num": 0,
    }
    stop_doc: RunStop = {
        "exit_status": "success",
        "run_start": "123",
        "uid": "456",
        "time": 0,
    }

    test_cb.active = True
    receiving_cb.active = True

    test_cb.start(start_doc)
    receiving_cb.activity_gated_start.assert_called_with(start_doc)
    test_cb.descriptor(desc_doc)
    receiving_cb.activity_gated_descriptor.assert_called_with(desc_doc)
    test_cb.event(event_doc)
    receiving_cb.activity_gated_event.assert_called_with(event_doc)
    test_cb.stop(stop_doc)
    receiving_cb.activity_gated_stop.assert_called_with(stop_doc)
