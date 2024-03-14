from typing import Callable, Sequence

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


def gridscan_ispyb_with_zocalo():
    return GridscanISPyBCallback(emit=ZocaloCallback())


def rotation_ispyb_with_zocalo():
    return RotationISPyBCallback(emit=ZocaloCallback())


CallbackFactories = Sequence[Callable[[], CallbackBase]]
gridscan_callbacks: CallbackFactories = [
    GridscanNexusFileCallback,
    gridscan_ispyb_with_zocalo,
]
rotation_callbacks: CallbackFactories = [
    RotationNexusFileCallback,
    rotation_ispyb_with_zocalo,
]
