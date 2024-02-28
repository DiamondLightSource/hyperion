from __future__ import annotations

from dataclasses import dataclass

from hyperion.external_interaction.callbacks.abstract_plan_callback_collection import (
    AbstractPlanCallbackCollection,
)
from hyperion.external_interaction.callbacks.xray_centre.ispyb_callback import (
    GridscanISPyBCallback,
)
from hyperion.external_interaction.callbacks.xray_centre.nexus_callback import (
    GridscanNexusFileCallback,
)
from hyperion.external_interaction.callbacks.zocalo_callback import (
    ZocaloCallback,
)


@dataclass(frozen=True, order=True)
class XrayCentreCallbackCollection(AbstractPlanCallbackCollection):
    """Groups the callbacks for external interactions in the fast grid scan, and
    connects the Zocalo and ISPyB handlers. Cast to a list to pass it to
    Bluesky.preprocessors.subs_decorator()."""

    nexus_handler: GridscanNexusFileCallback = GridscanNexusFileCallback()
    ispyb_handler: GridscanISPyBCallback = GridscanISPyBCallback(emit=ZocaloCallback())
