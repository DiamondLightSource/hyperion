from typing import TypeVar

from daq_config_server.client import ConfigServer

from hyperion.log import LOGGER
from hyperion.parameters.constants import CONST

_CONFIG_SERVER: ConfigServer | None = None
T = TypeVar("T")


def config_server() -> ConfigServer:
    global _CONFIG_SERVER
    if _CONFIG_SERVER is None:
        _CONFIG_SERVER = ConfigServer(CONST.CONFIG_SERVER_URL, LOGGER)
    return _CONFIG_SERVER


def best_effort_get_feature_flag(flag_name: str, fallback: T = None) -> bool | T:
    return config_server().best_effort_get_feature_flag(flag_name, fallback)
