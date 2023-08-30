import pytest
import dataclasses
from unittest.mock import MagicMock, call
from ophyd.device import Device
from hyperion.utils.context import find_device_in_context, device_composite_from_context


class _DeviceType1(Device):
    pass


class _DeviceType2(Device):
    pass


def test_find_device_in_context():
    context = MagicMock()
    device = MagicMock(spec=Device)
    context.find_device.return_value = device

    found_device = find_device_in_context(context, "", expected_type=Device)  # type: ignore
    assert found_device == device


def find_device_in_context_with_wrong_type_raises_error():
    context = MagicMock()

    device = MagicMock(spec=_DeviceType1)
    context.find_device.return_value = device

    # Should not raise
    find_device_in_context(context, "", expected_type=_DeviceType1)

    with pytest.raises(ValueError):
        # Should raise
        find_device_in_context(context, "", expected_type=_DeviceType2)


def test_find_nonexistent_device_in_context_raises_error():
    context = MagicMock()
    context.find_device.return_value = None

    with pytest.raises(ValueError):
        find_device_in_context(context, "", Device)


def test_device_composite_from_context():
    context = MagicMock()

    @dataclasses.dataclass
    class _Composite():
        device1: _DeviceType1
        device2: _DeviceType2

    device1_instance = MagicMock(spec=_DeviceType1)
    device2_instance = MagicMock(spec=_DeviceType2)

    context.find_device = lambda name: {"device1": device1_instance, "device2": device2_instance}.get(name)

    composite = device_composite_from_context(context, _Composite)

    assert composite.device1 == device1_instance
    assert isinstance(composite.device1, _DeviceType1)

    assert composite.device2 == device2_instance
    assert isinstance(composite.device2, _DeviceType2)