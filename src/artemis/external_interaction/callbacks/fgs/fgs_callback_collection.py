from typing import NamedTuple

from artemis.external_interaction.callbacks.fgs.ispyb_callback import (
    FGSISPyBHandlerCallback,
)
from artemis.external_interaction.callbacks.fgs.nexus_callback import (
    FGSNexusFileHandlerCallback,
)
from artemis.external_interaction.callbacks.fgs.zocalo_callback import FGSZocaloCallback
from artemis.parameters import FullParameters


class FGSCallbackCollection(NamedTuple):
    """Groups the callbacks for external interactions in the fast grid scan, and
    connects the Zocalo and ISPyB handlers. Cast to a list to pass it to
    Bluesky.preprocessors.subs_decorator()."""

    # Callbacks are triggered in this order, which is important: ISPyB deposition must
    # be initialised before the Zocalo handler can do its thing.
    nexus_handler: FGSNexusFileHandlerCallback
    ispyb_handler: FGSISPyBHandlerCallback
    zocalo_handler: FGSZocaloCallback

    @classmethod
    def from_params(cls, parameters: FullParameters):
        nexus_handler = FGSNexusFileHandlerCallback(parameters)
        ispyb_handler = FGSISPyBHandlerCallback(parameters)
        zocalo_handler = FGSZocaloCallback(parameters, ispyb_handler)
        callback_collection = cls(
            nexus_handler=nexus_handler,
            ispyb_handler=ispyb_handler,
            zocalo_handler=zocalo_handler,
        )
        return callback_collection
