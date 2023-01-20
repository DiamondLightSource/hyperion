from ophyd import Device
from ophyd.log import logger as ophyd_logger


class InfoLoggingDevice(Device):
    def wait_for_connection(self, all_signals=False, timeout=2):
        class_name = self.__class__.__name__
        ophyd_logger.info(
            f"{class_name} waiting for connection, {'not' if all_signals else ''} waiting for all signals, timeout = {timeout}s.",
        )
        try:
            super().wait_for_connection(all_signals, timeout)
        except TimeoutError as e:
            ophyd_logger.error(f"{class_name} failed to connect.", exc_info=True)
            raise e
        else:
            ophyd_logger.info(f"{class_name} connected.")
