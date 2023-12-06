from threading import Thread
from time import sleep
from typing import Callable

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
from hyperion.parameters.cli import parse_cli_args
from hyperion.parameters.constants import CALLBACK_0MQ_PROXY_PORTS


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


def setup_logging():
    (
        logging_level,
        _,
        dev_mode,
        _,
    ) = parse_cli_args()
    set_up_logging_handlers(
        logging_level=logging_level,
        dev_mode=dev_mode,
        filename="hyperion_ispyb_callback.txt",
        logger=ISPYB_LOGGER,
    )
    set_up_logging_handlers(
        logging_level=logging_level,
        dev_mode=dev_mode,
        filename="hyperion_nexus_callback.txt",
        logger=NEXUS_LOGGER,
    )


def setup_threads():
    proxy = Proxy(*CALLBACK_0MQ_PROXY_PORTS)
    dispatcher = RemoteDispatcher(f"localhost:{CALLBACK_0MQ_PROXY_PORTS[1]}")

    def start_proxy():
        proxy.start()

    def start_dispatcher(callbacks: list[Callable]):
        [dispatcher.subscribe(cb) for cb in callbacks]
        dispatcher.subscribe(print)
        dispatcher.start()

    return proxy, dispatcher, start_proxy, start_dispatcher


def log_info(msg, *args, **kwargs):
    ISPYB_LOGGER.info(msg, *args, **kwargs)
    NEXUS_LOGGER.info(msg, *args, **kwargs)


def main():
    setup_logging()
    log_info("Hyperion callback process started.")

    callbacks = setup_callbacks()
    proxy, dispatcher, start_proxy, start_dispatcher = setup_threads()
    log_info("Created 0MQ proxy and local RemoteDispatcher.")

    proxy_thread = Thread(target=start_proxy, daemon=True)
    dispatcher_thread = Thread(target=start_dispatcher, args=[callbacks], daemon=True)

    log_info(f"Launching threads, with callbacks: {callbacks}")
    proxy_thread.start()
    dispatcher_thread.start()
    log_info("Proxy and dispatcher thread launched.")
    try:
        while proxy_thread.is_alive() and dispatcher_thread.is_alive():
            sleep(1)
    except KeyboardInterrupt:
        log_info("Main thread recieved interrupt - exiting.")
    else:
        log_info("Proxy or dispatcher thread ended - exiting.")


if __name__ == "__main":
    main()
