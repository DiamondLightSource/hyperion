from threading import Thread
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


def start_proxy():
    proxy = Proxy(*CALLBACK_0MQ_PROXY_PORTS)
    proxy.start()


def start_dispatcher(callbacks: list[Callable]):
    d = RemoteDispatcher(f"localhost:{CALLBACK_0MQ_PROXY_PORTS[1]}")
    [d.subscribe(cb) for cb in callbacks]
    d.start()


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


def main():
    setup_logging()

    ISPYB_LOGGER.info("Hyperion Ispyb/Zocalo callback process started")
    NEXUS_LOGGER.info("Hyperion Nexus callback process started")

    proxy_thread = Thread(target=start_proxy)
    dispatcher_thread = Thread(target=start_dispatcher)
    try:
        proxy_thread.start()
        dispatcher_thread.start()
        while True:
            pass
    finally:
        proxy_thread.join()
        dispatcher_thread.join()


if __name__ == "__main":
    main()
