from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from artemis.external_interaction.callbacks.fgs.ispyb_callback import (
    FGSISPyBHandlerCallback,
)
from artemis.external_interaction.callbacks.fgs.nexus_callback import (
    FGSNexusFileHandlerCallback,
)
from artemis.external_interaction.callbacks.fgs.zocalo_callback import FGSZocaloCallback

if TYPE_CHECKING:
    from artemis.parameters.internal_parameters import InternalParameters


class FGSCallbackCollection(NamedTuple):
    """Groups the callbacks for external interactions in the fast grid scan, and
    connects the Zocalo and ISPyB handlers. Cast to a list to pass it to
    Bluesky.preprocessors.subs_decorator()."""

    nexus_handler: FGSNexusFileHandlerCallback
    ispyb_handler: FGSISPyBHandlerCallback
    zocalo_handler: FGSZocaloCallback

    @classmethod
    def from_params(cls, parameters: InternalParameters):
        nexus_handler = FGSNexusFileHandlerCallback(parameters)
        ispyb_handler = FGSISPyBHandlerCallback(parameters)
        zocalo_handler = FGSZocaloCallback(parameters, ispyb_handler)
        callback_collection = cls(
            nexus_handler=nexus_handler,
            ispyb_handler=ispyb_handler,
            zocalo_handler=zocalo_handler,
        )
        return callback_collection
