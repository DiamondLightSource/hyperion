from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from artemis.external_interaction.callbacks.abstract_plan_callback_collection import (
    AbstractPlanCallbackCollection,
)
from artemis.external_interaction.callbacks.rotation.ispyb_callback import (
    RotationISPyBHandlerCallback,
)
from artemis.external_interaction.callbacks.rotation.nexus_callback import (
    RotationNexusFileHandlerCallback,
)
from artemis.external_interaction.callbacks.rotation.zocalo_callback import (
    RotationZocaloHandlerCallback,
)

if TYPE_CHECKING:
    from artemis.parameters.plan_specific.rotation_scan_internal_params import (
        RotationInternalParameters,
    )


@dataclass(frozen=True, order=True)
class RotationCallbackCollection(AbstractPlanCallbackCollection):
    """Groups the callbacks for external interactions for a rotation scan.
    Cast to a list to pass it to Bluesky.preprocessors.subs_decorator()."""

    nexus_handler: RotationNexusFileHandlerCallback
    ispyb_handler: RotationISPyBHandlerCallback
    zocalo_handler: RotationZocaloHandlerCallback

    @classmethod
    def from_params(cls, parameters: RotationInternalParameters):
        nexus_handler = RotationNexusFileHandlerCallback()
        ispyb_handler = RotationISPyBHandlerCallback(parameters)
        zocalo_handler = RotationZocaloHandlerCallback(
            parameters.artemis_params.zocalo_environment, ispyb_handler
        )
        callback_collection = cls(
            nexus_handler=nexus_handler,
            ispyb_handler=ispyb_handler,
            zocalo_handler=zocalo_handler,
        )
        return callback_collection
