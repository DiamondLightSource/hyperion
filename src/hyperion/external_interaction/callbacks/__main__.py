from hyperion.__main__ import cli_arg_parse
from hyperion.log import ISPYB_LOGGER, NEXUS_LOGGER, set_up_logging_handlers


def main():
    (
        logging_level,
        _,
        dev_mode,
        _,
    ) = cli_arg_parse()
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
    ISPYB_LOGGER.info("Hyperion Ispyb/Zocalo callback process started")
    NEXUS_LOGGER.info("Hyperion Nexus callback process started")


if __name__ == "__main":
    main()
