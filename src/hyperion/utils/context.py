import dataclasses
from typing import Any, ClassVar, Dict, Protocol, Type, TypeVar, get_type_hints

from blueapi.core import BlueskyContext
from blueapi.core.bluesky_types import Device

# Ideally wouldn't import a 'private' method from dodal - but this will likely go
# away once we fully use blueapi's plan management components.
# https://github.com/DiamondLightSource/hyperion/issues/868
from dodal.utils import get_beamline_based_on_environment_variable

import hyperion.experiment_plans as hyperion_plans
from hyperion.log import LOGGER

T = TypeVar("T", bound=Device)


class _IsDataclass(Protocol):
    """Protocol followed by any dataclass"""

    __dataclass_fields__: ClassVar[Dict]


DT = TypeVar("DT", bound=_IsDataclass)


def find_device_in_context(
    context: BlueskyContext, name: str, expected_type: Type[T] = Device
) -> T:
    LOGGER.debug(f"Looking for device {name} of type {expected_type} in context")

    device = context.find_device(name)
    if device is None:
        raise ValueError(
            f"Cannot find device named '{name}' in bluesky context {context.devices}."
        )

    if not isinstance(device, expected_type):
        raise ValueError(
            f"Found device named '{name}' and expected it to be a '{expected_type}' but it was a '{device.__class__.__name__}'"
        )

    LOGGER.debug(f"Found matching device {device}")
    return device


def device_composite_from_context(context: BlueskyContext, dc: Type[DT]) -> DT:
    """
    Initializes all of the devices referenced in a given dataclass from a provided
    context, checking that the types of devices returned by the context are compatible
    with the type annotations of the dataclass.

    Note that if the context was not created with `wait_for_connection=True` devices may
    still be unconnected.
    """
    LOGGER.debug(
        f"Attempting to initialize devices referenced in dataclass {dc} from blueapi context"
    )

    devices: Dict[str, Any] = {}
    dc_type_hints: Dict[str, Any] = get_type_hints(dc)

    for field in dataclasses.fields(dc):
        device = find_device_in_context(
            context, field.name, expected_type=dc_type_hints.get(field.name, Device)
        )

        devices[field.name] = device

    return dc(**devices)


def setup_context(wait_for_connection: bool = True) -> BlueskyContext:
    context = BlueskyContext()
    context.with_plan_module(hyperion_plans)

    context.with_dodal_module(
        get_beamline_based_on_environment_variable(),
        wait_for_connection=wait_for_connection,
    )

    LOGGER.info(f"Plans found in context: {context.plan_functions.keys()}")

    return context
