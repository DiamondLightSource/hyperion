import pytest
from mockito import *
from src.artemis.devices.zebra import (
    GateControl,
    LogicGateConfiguration,
    boolean_array_to_integer,
    LogicGateConfigurer,
    GateType,
)
from ophyd.sim import make_fake_device


@pytest.mark.parametrize(
    "boolean_array,expected_integer",
    [
        ([True, False, False], 1),
        ([True, False, True, False], 5),
        ([False, True, False, True], 10),
        ([False, False, False, False], 0),
        ([True, True, True], 7),
    ],
)
def test_boolean_array_to_integer(boolean_array, expected_integer):
    assert boolean_array_to_integer(boolean_array) == expected_integer


def test_logic_gate_configuration_23():
    config1 = LogicGateConfiguration(23)
    assert config1.sources == [23]
    assert config1.invert == [False]
    assert str(config1) == "INP1=23"


def test_logic_gate_configuration_43_and_14_inv():
    config = LogicGateConfiguration(43).add_input(14, True)
    assert config.sources == [43, 14]
    assert config.invert == [False, True]
    assert str(config) == "INP1=43, INP2=!14"


def test_logic_gate_configuration_62_and_34_inv_and_15_inv():
    config = LogicGateConfiguration(62).add_input(34, True).add_input(15, True)
    assert config.sources == [62, 34, 15]
    assert config.invert == [False, True, True]
    assert str(config) == "INP1=62, INP2=!34, INP3=!15"


def run_configurer_test(gate_type: GateType, gate_num, config, expected_pv_values):
    FakeLogicConfigurer = make_fake_device(LogicGateConfigurer)
    configurer = FakeLogicConfigurer(name="test")

    mock_gate_control = mock()
    mock_pvs = [mock() for i in range(6)]
    mock_gate_control.enable = mock_pvs[0]
    mock_gate_control.sources = mock_pvs[1:5]
    mock_gate_control.invert = mock_pvs[5]
    configurer.all_gates[gate_type][gate_num - 1] = mock_gate_control

    if gate_type == GateType.AND:
        configurer.apply_and_gate_config(gate_num, config)
    else:
        configurer.apply_or_gate_config(gate_num, config)

    for pv, value in zip(mock_pvs, expected_pv_values):
        verify(pv).put(value)


@pytest.mark.skip("Will fail until https://github.com/bluesky/ophyd/pull/1023 is merged")
def test_apply_and_logic_gate_configuration_32_and_51_inv_and_1():
    config = LogicGateConfiguration(32).add_input(51, True).add_input(1)
    expected_pv_values = [7, 32, 51, 1, 0, 2]

    run_configurer_test(GateType.AND, 1, config, expected_pv_values)


@pytest.mark.skip("Will fail until https://github.com/bluesky/ophyd/pull/1023 is merged")
def test_apply_or_logic_gate_configuration_19_and_36_inv_and_60_inv():
    config = LogicGateConfiguration(19).add_input(36, True).add_input(60, True)
    expected_pv_values = [7, 19, 36, 60, 0, 6]

    run_configurer_test(GateType.OR, 2, config, expected_pv_values)


@pytest.mark.parametrize(
    "source",
    [
        -1,
        67
    ],
)
def test_logic_gate_configuration_with_invalid_source_then_error(source):
    with pytest.raises(AssertionError):
        LogicGateConfiguration(source)

    existing_config = LogicGateConfiguration(1)
    with pytest.raises(AssertionError):
        existing_config.add_input(source)

def test_logic_gate_configuration_with_too_many_sources_then_error():
    config = LogicGateConfiguration(0)
    for source in range(1,4):
        config.add_input(source)

    with pytest.raises(AssertionError):
        config.add_input(5)
