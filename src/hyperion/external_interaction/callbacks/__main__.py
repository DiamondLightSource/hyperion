import logging
from threading import Thread
from time import sleep
from typing import Callable, Sequence

from bluesky.callbacks.zmq import Proxy, RemoteDispatcher
from dodal.log import set_up_all_logging_handlers

from hyperion.external_interaction.callbacks.rotation.ispyb_callback import (
    RotationISPyBCallback,
)
from hyperion.external_interaction.callbacks.rotation.nexus_callback import (
    RotationNexusFileCallback,
)
from hyperion.external_interaction.callbacks.xray_centre.ispyb_callback import (
    GridscanISPyBCallback,
)
from hyperion.external_interaction.callbacks.xray_centre.nexus_callback import (
    GridscanNexusFileCallback,
)
from hyperion.external_interaction.callbacks.zocalo_callback import (
    ZocaloCallback,
)
from hyperion.log import (
    ISPYB_LOGGER,
    NEXUS_LOGGER,
    _get_logging_dir,
    dc_group_id_filter,
)
from hyperion.parameters.cli import parse_callback_dev_mode_arg
from hyperion.parameters.constants import CONST

LIVENESS_POLL_SECONDS = 1
ERROR_LOG_BUFFER_LINES = 5000


def setup_callbacks():
    zocalo = ZocaloCallback()
    return [
        GridscanNexusFileCallback(),
        GridscanISPyBCallback(emit=zocalo),
        RotationNexusFileCallback(),
        RotationISPyBCallback(emit=zocalo),
    ]


def setup_logging(dev_mode: bool):
    for logger, filename in [
        (ISPYB_LOGGER, "hyperion_ispyb_callback.txt"),
        (NEXUS_LOGGER, "hyperion_nexus_callback.txt"),
    ]:
        if logger.handlers == []:
            handlers = set_up_all_logging_handlers(
                logger,
                _get_logging_dir(),
                filename,
                dev_mode,
                error_log_buffer_lines=ERROR_LOG_BUFFER_LINES,
            )
            handlers["graylog_handler"].addFilter(dc_group_id_filter)
    log_info(f"Loggers initialised with dev_mode={dev_mode}")
    nexgen_logger = logging.getLogger("nexgen")
    nexgen_logger.parent = NEXUS_LOGGER
    log_debug("nexgen logger added to nexus logger")


def setup_threads():
    proxy = Proxy(*CONST.CALLBACK_0MQ_PROXY_PORTS)
    dispatcher = RemoteDispatcher(f"localhost:{CONST.CALLBACK_0MQ_PROXY_PORTS[1]}")
    log_debug("Created proxy and dispatcher objects")

    def start_proxy():
        proxy.start()

    def start_dispatcher(callbacks: list[Callable]):
        [dispatcher.subscribe(cb) for cb in callbacks]
        dispatcher.start()

    return proxy, dispatcher, start_proxy, start_dispatcher


def log_info(msg, *args, **kwargs):
    ISPYB_LOGGER.info(msg, *args, **kwargs)
    NEXUS_LOGGER.info(msg, *args, **kwargs)


def log_debug(msg, *args, **kwargs):
    ISPYB_LOGGER.debug(msg, *args, **kwargs)
    NEXUS_LOGGER.debug(msg, *args, **kwargs)


def wait_for_threads_forever(threads: Sequence[Thread]):
    alive = [t.is_alive() for t in threads]
    try:
        log_debug("Trying to wait forever on callback and dispatcher threads")
        while all(alive):
            sleep(LIVENESS_POLL_SECONDS)
            alive = [t.is_alive() for t in threads]
    except KeyboardInterrupt:
        log_info("Main thread recieved interrupt - exiting.")
    else:
        log_info("Proxy or dispatcher thread ended - exiting.")


class HyperionCallbackRunner:
    """Runs Nexus, ISPyB and Zocalo callbacks in their own process."""

    def __init__(self, dev_mode) -> None:
        setup_logging(dev_mode)
        log_info("Hyperion callback process started.")

        self.callbacks = setup_callbacks()
        self.proxy, self.dispatcher, start_proxy, start_dispatcher = setup_threads()
        log_info("Created 0MQ proxy and local RemoteDispatcher.")

        self.proxy_thread = Thread(target=start_proxy, daemon=True)
        self.dispatcher_thread = Thread(
            target=start_dispatcher, args=[self.callbacks], daemon=True
        )

    def start(self):
        log_info(f"Launching threads, with callbacks: {self.callbacks}")
        self.proxy_thread.start()
        self.dispatcher_thread.start()
        log_info("Proxy and dispatcher thread launched.")
        wait_for_threads_forever([self.proxy_thread, self.dispatcher_thread])


def main(dev_mode=False) -> None:
    dev_mode = dev_mode or parse_callback_dev_mode_arg()
    print(f"In dev mode: {dev_mode}")
    runner = HyperionCallbackRunner(dev_mode)
    runner.start()


if __name__ == "__main__":
    main()
