from typing import NamedTuple, Optional

from artemis.external_interaction.callbacks.fgs.ispyb_callback import (
    FGSISPyBHandlerCallback,
)
from artemis.external_interaction.callbacks.fgs.logging_callback import (
    VerbosePlanExecutionLoggingCallback,
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
    # Optionally we can log all the documents
    event_logger: Optional[VerbosePlanExecutionLoggingCallback]

    def get_list(self) -> list:
        """Returns a list() of the callbacks in this collection, but not including the
        verbose event logger if it is None."""
        return [c for c in list(self) if c is not None]

    @classmethod
    def from_params(
        cls, parameters: FullParameters, verbose_event_logging: Optional[bool] = None
    ):
        nexus_handler = FGSNexusFileHandlerCallback(parameters)
        ispyb_handler = FGSISPyBHandlerCallback(parameters)
        zocalo_handler = FGSZocaloCallback(parameters, ispyb_handler)
        if verbose_event_logging:
            callback_collection = cls(
                nexus_handler=nexus_handler,
                ispyb_handler=ispyb_handler,
                zocalo_handler=zocalo_handler,
                event_logger=VerbosePlanExecutionLoggingCallback(),
            )
        else:
            callback_collection = cls(
                nexus_handler=nexus_handler,
                ispyb_handler=ispyb_handler,
                zocalo_handler=zocalo_handler,
                event_logger=None,
            )
        return callback_collection
