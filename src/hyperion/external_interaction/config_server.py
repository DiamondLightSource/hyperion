from typing import TypeVar

from daq_config_server.client import ConfigServer
from pydantic import BaseModel

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


class FeatureFlags(BaseModel):
    # The default value will be used as the fallback when doing a best-effort fetch
    # from the service
    use_panda_for_gridscan: bool = False
    use_gpu_for_gridscan: bool = False
    set_stub_offsets: bool = False

    @classmethod
    def best_effort(cls):
        flags = {
            field_name: best_effort_get_feature_flag(field_name, field_details.default)
            for (field_name, field_details) in cls.__fields__.items()
        }
        return cls(**flags)
