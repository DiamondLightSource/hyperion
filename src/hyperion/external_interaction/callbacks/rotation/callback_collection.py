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
from hyperion.external_interaction.callbacks.zocalo_callback import (
    ZocaloCallback,
)


@dataclass(frozen=True, order=True)
class RotationCallbackCollection(AbstractPlanCallbackCollection):
    """Groups the callbacks for external interactions for a rotation scan.
    Cast to a list to pass it to Bluesky.preprocessors.subs_decorator()."""

    nexus_handler: RotationNexusFileCallback = RotationNexusFileCallback()
    ispyb_handler: RotationISPyBCallback = RotationISPyBCallback(emit=ZocaloCallback())
