import logging
from threading import Thread
from time import sleep
from typing import Callable, Sequence

from bluesky.callbacks.zmq import Proxy, RemoteDispatcher

from hyperion.external_interaction.callbacks.rotation.ispyb_callback import (
    RotationISPyBCallback,
)
from hyperion.external_interaction.callbacks.rotation.nexus_callback import (
    RotationNexusFileCallback,
)
from hyperion.external_interaction.callbacks.rotation.zocalo_callback import (
    RotationZocaloCallback,
)
from hyperion.external_interaction.callbacks.xray_centre.ispyb_callback import (
    GridscanISPyBCallback,
)
from hyperion.external_interaction.callbacks.xray_centre.nexus_callback import (
    GridscanNexusFileCallback,
)
from hyperion.external_interaction.callbacks.xray_centre.zocalo_callback import (
    XrayCentreZocaloCallback,
)
from hyperion.log import ISPYB_LOGGER, NEXUS_LOGGER, set_up_logging_handlers
from hyperion.parameters.cli import CallbackArgs, parse_callback_cli_args
from hyperion.parameters.constants import CALLBACK_0MQ_PROXY_PORTS

LIVENESS_POLL_SECONDS = 1


def setup_callbacks():
    gridscan_ispyb = GridscanISPyBCallback()
    rotation_ispyb = RotationISPyBCallback()
    return [
        GridscanNexusFileCallback(),
        gridscan_ispyb,
        XrayCentreZocaloCallback(gridscan_ispyb),
        RotationNexusFileCallback(),
        rotation_ispyb,
        RotationZocaloCallback(rotation_ispyb),
    ]


def setup_logging(logging_args: CallbackArgs):
    set_up_logging_handlers(
        logging_level=logging_args.logging_level,
        dev_mode=logging_args.dev_mode,
        filename="hyperion_ispyb_callback.txt",
        logger=ISPYB_LOGGER,
    )
    set_up_logging_handlers(
        logging_level=logging_args.logging_level,
        dev_mode=logging_args.dev_mode,
        filename="hyperion_nexus_callback.txt",
        logger=NEXUS_LOGGER,
    )
    log_info(f"Loggers initialised with arguments: {logging_args}")
    nexgen_logger = logging.getLogger("nexgen")
    nexgen_logger.parent = NEXUS_LOGGER
    log_debug("nexgen logger added to nexus logger")


def setup_threads():
    proxy = Proxy(*CALLBACK_0MQ_PROXY_PORTS)
    dispatcher = RemoteDispatcher(f"localhost:{CALLBACK_0MQ_PROXY_PORTS[1]}")
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

    def __init__(self, logging_args) -> None:
        setup_logging(logging_args)
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


def main(logging_args=None) -> None:
    logging_args = logging_args or parse_callback_cli_args()
    print(f"using logging args {logging_args}")
    runner = HyperionCallbackRunner(logging_args)
    runner.start()


if __name__ == "__main__":
    main()
