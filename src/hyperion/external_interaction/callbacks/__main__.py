from threading import Thread

from bluesky.callbacks.zmq import Proxy, RemoteDispatcher

from hyperion.log import ISPYB_LOGGER, NEXUS_LOGGER, set_up_logging_handlers
from hyperion.parameters.cli import parse_cli_args
from hyperion.parameters.constants import CALLBACK_0MQ_PROXY_PORTS


def start_proxy():
    proxy = Proxy(*CALLBACK_0MQ_PROXY_PORTS)
    proxy.start()


def start_dispatcher():
    d = RemoteDispatcher(f"localhost:{CALLBACK_0MQ_PROXY_PORTS[1]}")
    d.subscribe(print)
    d.start()


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
