from __future__ import annotations

from dataclasses import dataclass

from hyperion.external_interaction.callbacks.abstract_plan_callback_collection import (
    AbstractPlanCallbackCollection,
)
from hyperion.external_interaction.callbacks.xray_centre.ispyb_callback import (
    GridscanISPyBCallback,
)
from hyperion.external_interaction.callbacks.xray_centre.nexus_callback import (
    GridscanNexusFileCallback,
)
from hyperion.external_interaction.callbacks.zocalo_callback import (
    ZocaloCallback,
)
from hyperion.parameters.constants import DO_FGS


@dataclass(frozen=True, order=True)
class XrayCentreCallbackCollection(AbstractPlanCallbackCollection):
    """Groups the callbacks for external interactions in the fast grid scan, and
    connects the Zocalo and ISPyB handlers. Cast to a list to pass it to
    Bluesky.preprocessors.subs_decorator()."""

    nexus_handler: GridscanNexusFileCallback
    ispyb_handler: GridscanISPyBCallback
    zocalo_handler: ZocaloCallback

    @classmethod
    def setup(cls):
        nexus_handler = GridscanNexusFileCallback()
        ispyb_handler = GridscanISPyBCallback()
        zocalo_handler = ZocaloCallback(ispyb_handler, DO_FGS)
        callback_collection = cls(
            nexus_handler=nexus_handler,
            ispyb_handler=ispyb_handler,
            zocalo_handler=zocalo_handler,
        )
        return callback_collection
