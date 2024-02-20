from __future__ import annotations

from hyperion.external_interaction.ispyb.gridscan_ispyb_store import (
    StoreGridscanInIspyb,
)


class Store2DGridscanInIspyb(StoreGridscanInIspyb):
    def __init__(self, ispyb_config: str):
        super().__init__(ispyb_config)

    @property
    def experiment_type(self) -> str:
        return "mesh"
