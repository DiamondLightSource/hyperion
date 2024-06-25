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


class FeatureFlags(BaseModel):
    # The default value will be used as the fallback when doing a best-effort fetch
    # from the service
    use_panda_for_gridscan: bool = False
    use_gpu_for_gridscan: bool = False
    set_stub_offsets: bool = False

    @classmethod
    def _get_flags(cls):
        flags = config_server().best_effort_get_all_feature_flags()
        return {f: flags[f] for f in flags if f in cls.__fields__.keys()}

    @classmethod
    def best_effort(cls):
        return cls(**cls._get_flags())

    def update_self_from_server(self):
        for flag, value in self._get_flags().items():
            setattr(self, flag, value)
