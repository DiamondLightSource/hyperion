from unittest.mock import MagicMock

import pytest
from bluesky.run_engine import RunEngine

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

    class MockTestException(Exception):
        ...

    e = MockTestException()

    def mock_excepting_func(_):
        raise e

    cb.log = MagicMock()

    with pytest.raises(MockTestException):
        cb._run_activity_gated(mock_excepting_func, {"start": "test"})

    cb.log.exception.assert_called_with(e)
