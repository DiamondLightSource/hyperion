import dataclasses
import inspect
from typing import Any, ClassVar, Dict, Protocol, Type, TypeVar, Union, get_type_hints

from blueapi.core import BlueskyContext
from blueapi.core.bluesky_types import Device

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
        raise ValueError(f"Cannot find device named '{name}' in bluesky context.")

    if not isinstance(device, expected_type):
        raise ValueError(
            f"Found device named '{name}' and expected it to be a '{expected_type}' but it was a '{device.__class__.__name__}'"
        )

    LOGGER.debug(f"Found matching device {device}")
    return device


def initialise_devices_in_composite(context: BlueskyContext, dc: Type[DT]) -> DT:
    """
    Initializes all of the devices referenced in a given dataclass from a provided
    context, checking that the types of devices returned by the context are compatible
    with the type annotations of the dataclass.
    """
    LOGGER.debug(
        f"Attempting to initialize devices referenced in dataclass {dc} from blueapi context"
    )

    devices: Dict[str, Any] = {}
    dc_type_hints: Dict[str, Any] = get_type_hints(dc)

    for field in dataclasses.fields(dc):
        devices[field.name] = find_device_in_context(
            context, field.name, dc_type_hints.get(field.name, Device)
        )

    return dc(**devices)
