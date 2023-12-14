from threading import Lock, Thread
from time import sleep
from typing import Sequence
from unittest.mock import MagicMock, patch

import pytest
from bluesky.callbacks.zmq import Publisher
from bluesky.run_engine import RunEngine

from hyperion.__main__ import CALLBACK_0MQ_PROXY_PORTS
from hyperion.external_interaction.callbacks.__main__ import (
    HyperionCallbackRunner,
    main,
    setup_callbacks,
    setup_logging,
)
from hyperion.log import ISPYB_LOGGER, NEXUS_LOGGER

from ..conftest import MockReactiveCallback, get_test_plan


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
    setup_logging()
    assert len(ISPYB_LOGGER.handlers) == 3
    assert len(NEXUS_LOGGER.handlers) == 3


@pytest.mark.skip(reason="Run this test on its own; will hang if they are run all at once.")
@patch("hyperion.external_interaction.callbacks.__main__.wait_for_threads_forever")
@patch("hyperion.external_interaction.callbacks.__main__.setup_logging")
@patch("hyperion.external_interaction.callbacks.__main__.setup_callbacks")
def test_publisher_connects_to_remote_dispatcher(
    setup_callbacks: MagicMock,
    setup_logging: MagicMock,
    wait_forever: MagicMock,
    RE: RunEngine,
):
    test_cb = MockReactiveCallback()
    setup_callbacks.return_value = [test_cb]
    thread_lock = Lock()
    thread_lock.acquire()

    def fake_wait_forever(threads: Sequence[Thread]):
        while thread_lock.locked():
            sleep(0.01)

    wait_forever.side_effect = fake_wait_forever

    runner = HyperionCallbackRunner()
    remote_thread = Thread(target=main, args=[runner])
    remote_thread.start()

    while wait_forever.call_count == 0:
        sleep(0.01)  # Wait for other threads to actually start up

    publisher = Publisher(f"localhost:{CALLBACK_0MQ_PROXY_PORTS[0]}")
    RE.subscribe(publisher)
    RE(get_test_plan("MockReactiveCallback")[0]())

    thread_lock.release()
    remote_thread.join()
    assert not remote_thread.is_alive()

    test_cb.activity_gated_start.assert_called_once()
    test_cb.activity_gated_descriptor.assert_called_once()
    test_cb.activity_gated_event.assert_called_once()
    test_cb.activity_gated_stop.assert_called_once()
