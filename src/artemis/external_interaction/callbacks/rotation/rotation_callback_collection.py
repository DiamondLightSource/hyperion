from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from artemis.external_interaction.callbacks.abstract_plan_callback_collection import (
    AbstractPlanCallbackCollection,
)
from artemis.external_interaction.callbacks.rotation.nexus_callback import (
    RotationNexusFileHandlerCallback,
)

if TYPE_CHECKING:
    from artemis.parameters.internal_parameters import InternalParameters


@dataclass(frozen=True, order=True)
class RotationCallbackCollection(AbstractPlanCallbackCollection):
    """Groups the callbacks for external interactions in the fast grid scan, and
    connects the Zocalo and ISPyB handlers. Cast to a list to pass it to
    Bluesky.preprocessors.subs_decorator()."""

    nexus_handler: RotationNexusFileHandlerCallback

    @classmethod
    def from_params(cls, parameters: InternalParameters):
        nexus_handler = RotationNexusFileHandlerCallback(parameters)
        callback_collection = cls(
            nexus_handler=nexus_handler,
        )
        return callback_collection
