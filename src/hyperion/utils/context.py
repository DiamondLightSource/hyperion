import dataclasses
import importlib
import os
import string
from types import ModuleType
from typing import Any, ClassVar, Dict, Protocol, Type, TypeVar, get_type_hints

from blueapi.core import BlueskyContext
from blueapi.core.bluesky_types import Device
from dodal.utils import get_beamline_name, make_all_devices

# Ideally wouldn't import a 'private' method from dodal - but this will likely go
# away once we fully use blueapi's plan management components.
from dodal.beamlines.beamline_utils import _wait_for_connection

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
        raise ValueError(f"Cannot find device named '{name}' in bluesky context.")

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

    Will ensure that devices referenced by this composite are connected.
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

        # At the point where we're actually making a device composite, i.e. starting a plan with these devices,
        # we need all the referenced devices to be connected.
        _wait_for_connection(device=device)

        devices[field.name] = device

    return dc(**devices)


def _get_beamline_specific_device_module() -> ModuleType:
    beamline = get_beamline_name("")

    if beamline == "":
        raise ValueError(
            "Cannot determine beamline - BEAMLINE environment variable not set."
        )

    beamline = beamline.replace("-", "_")
    valid_characters = string.ascii_letters + string.digits + "_"

    if (
        len(beamline) == 0
        or beamline[0] not in string.ascii_letters
        or not all(c in valid_characters for c in beamline)
    ):
        raise ValueError(
            "Invalid BEAMLINE variable - module name is not a permissible python module name, got '{}'".format(
                beamline
            )
        )

    try:
        return importlib.import_module("dodal.beamlines.{}".format(beamline))
    except ImportError as e:
        raise ValueError(
            "Hyperion failed to import beamline-specific dodal module 'dodal.beamlines.{}'".format(
                beamline
            )
        ) from e


def setup_context(
    wait_for_connection: bool = True, fake_with_ophyd_sim: bool = False
) -> BlueskyContext:
    context = BlueskyContext()
    context.with_plan_module(hyperion_plans)

    # Ideally would use context.with_dodal_device_module, but it doesn't support
    # passing through wait_for_connection or fake_with_ophyd_sim
    # TODO: create blueapi issue/PR
    for name, device in make_all_devices(
        _get_beamline_specific_device_module(),
        wait_for_connection=wait_for_connection,
        fake_with_ophyd_sim=fake_with_ophyd_sim,
    ).items():
        context.device(device, name=name)

    return context
