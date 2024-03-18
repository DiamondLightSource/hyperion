from typing import Callable, Tuple

from bluesky.callbacks import CallbackBase

from hyperion.external_interaction.callbacks.rotation.ispyb_callback import (
    RotationISPyBCallback,
)
from hyperion.external_interaction.callbacks.rotation.nexus_callback import (
    RotationNexusFileCallback,
)
from hyperion.external_interaction.callbacks.xray_centre.ispyb_callback import (
    GridscanISPyBCallback,
)
from hyperion.external_interaction.callbacks.xray_centre.nexus_callback import (
    GridscanNexusFileCallback,
)
from hyperion.external_interaction.callbacks.zocalo_callback import ZocaloCallback

CallbacksFactory = Callable[[], Tuple[CallbackBase, CallbackBase]]


def create_gridscan_callbacks() -> (
    Tuple[GridscanNexusFileCallback, GridscanISPyBCallback]
):
    return (GridscanNexusFileCallback(), GridscanISPyBCallback(emit=ZocaloCallback()))


def create_rotation_callbacks() -> (
    Tuple[RotationNexusFileCallback, RotationISPyBCallback]
):
    return (RotationNexusFileCallback(), RotationISPyBCallback(emit=ZocaloCallback()))
