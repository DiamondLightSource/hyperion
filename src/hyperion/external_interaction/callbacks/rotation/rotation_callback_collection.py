from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from hyperion.external_interaction.callbacks.abstract_plan_callback_collection import (
    AbstractPlanCallbackCollection,
)
from hyperion.external_interaction.callbacks.rotation.ispyb_callback import (
    RotationISPyBCallback,
)
from hyperion.external_interaction.callbacks.rotation.nexus_callback import (
    RotationNexusFileCallback,
)
from hyperion.external_interaction.callbacks.rotation.zocalo_callback import (
    RotationZocaloCallback,
)

if TYPE_CHECKING:
    from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
        RotationInternalParameters,
    )


@dataclass(frozen=True, order=True)
class RotationCallbackCollection(AbstractPlanCallbackCollection):
    """Groups the callbacks for external interactions for a rotation scan.
    Cast to a list to pass it to Bluesky.preprocessors.subs_decorator()."""

    nexus_handler: RotationNexusFileCallback
    ispyb_handler: RotationISPyBCallback
    zocalo_handler: RotationZocaloCallback

    @classmethod
    def from_params(cls, parameters: RotationInternalParameters):
        nexus_handler = RotationNexusFileCallback()
        ispyb_handler = RotationISPyBCallback(parameters)
        zocalo_handler = RotationZocaloCallback(
            parameters.hyperion_params.zocalo_environment, ispyb_handler
        )
        callback_collection = cls(
            nexus_handler=nexus_handler,
            ispyb_handler=ispyb_handler,
            zocalo_handler=zocalo_handler,
        )
        return callback_collection
