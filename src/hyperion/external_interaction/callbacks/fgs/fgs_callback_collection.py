from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from hyperion.external_interaction.callbacks.abstract_plan_callback_collection import (
    AbstractPlanCallbackCollection,
)
from hyperion.external_interaction.callbacks.fgs.ispyb_callback import FGSISPyBCallback
from hyperion.external_interaction.callbacks.fgs.nexus_callback import (
    FGSNexusFileCallback,
)
from hyperion.external_interaction.callbacks.fgs.zocalo_callback import (
    FGSZocaloCallback,
)

if TYPE_CHECKING:
    from hyperion.parameters.internal_parameters import InternalParameters


@dataclass(frozen=True, order=True)
class FGSCallbackCollection(AbstractPlanCallbackCollection):
    """Groups the callbacks for external interactions in the fast grid scan, and
    connects the Zocalo and ISPyB handlers. Cast to a list to pass it to
    Bluesky.preprocessors.subs_decorator()."""

    nexus_handler: FGSNexusFileCallback
    ispyb_handler: FGSISPyBCallback
    zocalo_handler: FGSZocaloCallback

    @classmethod
    def from_params(cls, parameters: InternalParameters):
        nexus_handler = FGSNexusFileCallback()
        ispyb_handler = FGSISPyBCallback(parameters)
        zocalo_handler = FGSZocaloCallback(parameters, ispyb_handler)
        callback_collection = cls(
            nexus_handler=nexus_handler,
            ispyb_handler=ispyb_handler,
            zocalo_handler=zocalo_handler,
        )
        return callback_collection
