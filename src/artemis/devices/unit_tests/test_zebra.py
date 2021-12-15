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
        ([True, False, False, False], 1),
        ([True, False, True, False], 5),
        ([False, True, False, True], 10),
        ([False, False, False, False], 0),
        ([True, True, True, True], 15),
    ],
)
def test_boolean_array_to_integer(boolean_array, expected_integer):
    assert boolean_array_to_integer(boolean_array) == expected_integer


def test_logic_gate_configuration_1_23():
    config1 = LogicGateConfiguration(1, 23)
    assert config1.use == [True, False, False, False]
    assert config1.sources == [23, 0, 0, 0]
    assert config1.invert == [False, False, False, False]
    assert str(config1) == "INP1=23"


def test_logic_gate_configuration_2_43_and_3_14_inv():
    config = LogicGateConfiguration(2, 43).add_input(3, 14, True)
    assert config.use == [False, True, True, False]
    assert config.sources == [0, 43, 14, 0]
    assert config.invert == [False, False, True, False]
    assert str(config) == "INP2=43, INP3=!14"


def test_logic_gate_configuration_4_62_and_1_34_inv_and_2_15_inv():
    config = LogicGateConfiguration(4, 62).add_input(1, 34, True).add_input(2, 15, True)
    assert config.use == [True, True, False, True]
    assert config.sources == [34, 15, 0, 62]
    assert config.invert == [True, True, False, False]
    assert str(config) == "INP1=!34, INP2=!15, INP4=62"


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
def test_apply_and_logic_gate_configuration_1_32_and_2_51_inv_and_4_1():
    config = LogicGateConfiguration(1, 32).add_input(2, 51, True).add_input(4, 1)
    expected_pv_values = [11, 32, 51, 0, 1, 2]

    run_configurer_test(GateType.AND, 1, config, expected_pv_values)


@pytest.mark.skip("Will fail until https://github.com/bluesky/ophyd/pull/1023 is merged")
def test_apply_or_logic_gate_configuration_3_19_and_1_36_inv_and_2_60_inv():
    config = LogicGateConfiguration(3, 19).add_input(1, 36, True).add_input(2, 60, True)
    expected_pv_values = [7, 36, 60, 19, 0, 3]

    run_configurer_test(GateType.OR, 2, config, expected_pv_values)


@pytest.mark.parametrize(
    "input,source",
    [
        (0, 1),
        (5, 1),
        (1, -1),
        (1, 67),
    ],
)
def test_logic_gate_configuration_with_invalid_input_then_error(input, source):
    with pytest.raises(AssertionError):
        LogicGateConfiguration(input, source)

    existing_config = LogicGateConfiguration(1, 1)
    with pytest.raises(AssertionError):
        existing_config.add_input(input, source)
