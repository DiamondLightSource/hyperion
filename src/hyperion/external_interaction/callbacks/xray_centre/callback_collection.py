from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from hyperion.external_interaction.callbacks.abstract_plan_callback_collection import (
    AbstractPlanCallbackCollection,
)
from hyperion.external_interaction.callbacks.xray_centre.ispyb_callback import (
    GridscanISPyBCallback,
)
from hyperion.external_interaction.callbacks.xray_centre.nexus_callback import (
    Gridscan2DNexusFileCallback,
    GridscanNexusFileCallback,
)
from hyperion.external_interaction.callbacks.xray_centre.zocalo_callback import (
    XrayCentreZocaloCallback,
)
from hyperion.external_interaction.nexus.nexus_utils import (
    create_i03_goniometer_axes,
    create_vmxm_goniometer_axes,
)

if TYPE_CHECKING:
    from hyperion.parameters.internal_parameters import InternalParameters


@dataclass(frozen=True, order=True)
class XrayCentreCallbackCollection(AbstractPlanCallbackCollection):
    """Groups the callbacks for external interactions in the fast grid scan, and
    connects the Zocalo and ISPyB handlers. Cast to a list to pass it to
    Bluesky.preprocessors.subs_decorator().

    Note: currently specific to i03 as it creates i03's goniometer axes."""

    nexus_handler: GridscanNexusFileCallback
    ispyb_handler: GridscanISPyBCallback
    zocalo_handler: XrayCentreZocaloCallback

    @classmethod
    def from_params(cls, parameters: InternalParameters):
        nexus_handler = GridscanNexusFileCallback(create_i03_goniometer_axes)
        ispyb_handler = GridscanISPyBCallback(parameters)
        zocalo_handler = XrayCentreZocaloCallback(parameters, ispyb_handler)
        callback_collection = cls(
            nexus_handler=nexus_handler,
            ispyb_handler=ispyb_handler,
            zocalo_handler=zocalo_handler,
        )
        return callback_collection


@dataclass(frozen=True, order=True)
class VmxmFastGridScanCallbackCollection(AbstractPlanCallbackCollection):
    """Like XRayCentreCallbackCollection, but without zocalo.

    Note: currently specific to VMXm as it creates VMXm's goniometer axes."""

    nexus_handler: Gridscan2DNexusFileCallback
    ispyb_handler: GridscanISPyBCallback

    @classmethod
    def from_params(cls, parameters: InternalParameters):
        nexus_handler = Gridscan2DNexusFileCallback(create_vmxm_goniometer_axes)
        ispyb_handler = GridscanISPyBCallback(parameters)
        callback_collection = cls(
            nexus_handler=nexus_handler,
            ispyb_handler=ispyb_handler,
        )
        return callback_collection
