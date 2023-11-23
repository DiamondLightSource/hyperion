from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True, order=True)
class RotationCallbackCollection(AbstractPlanCallbackCollection):
    """Groups the callbacks for external interactions for a rotation scan.
    Cast to a list to pass it to Bluesky.preprocessors.subs_decorator()."""

    nexus_handler: RotationNexusFileCallback
    ispyb_handler: RotationISPyBCallback
    zocalo_handler: RotationZocaloCallback

    @classmethod
    def setup(cls):
        nexus_handler = RotationNexusFileCallback()
        ispyb_handler = RotationISPyBCallback()
        zocalo_handler = RotationZocaloCallback(ispyb_handler)
        callback_collection = cls(
            nexus_handler=nexus_handler,
            ispyb_handler=ispyb_handler,
            zocalo_handler=zocalo_handler,
        )
        return callback_collection
