from typing import NamedTuple

from artemis.external_interaction.communicator_callbacks import (
    ISPyBHandlerCallback,
    NexusFileHandlerCallback,
)
from artemis.external_interaction.zocalo_interaction import ZocaloHandlerCallback
from artemis.parameters import FullParameters


class FGSCallbackCollection(NamedTuple):
    """Groups the callbacks for external interactions in the fast grid scan, and
    connects the Zocalo and ISPyB handlers. Cast to a list to pass it to
    Bluesky.preprocessors.subs_decorator()."""

    # Callbacks are triggered in this order, which is important: ISPyB deposition must
    # be initialised before the Zocalo handler can do its thing.
    nexus_handler: NexusFileHandlerCallback
    ispyb_handler: ISPyBHandlerCallback
    zocalo_handler: ZocaloHandlerCallback

    @classmethod
    def from_params(cls, parameters: FullParameters):
        nexus_handler = NexusFileHandlerCallback(parameters)
        ispyb_handler = ISPyBHandlerCallback(parameters)
        zocalo_handler = ZocaloHandlerCallback(parameters, ispyb_handler)
        callback_collection = cls(
            nexus_handler=nexus_handler,
            ispyb_handler=ispyb_handler,
            zocalo_handler=zocalo_handler,
        )
        return callback_collection
