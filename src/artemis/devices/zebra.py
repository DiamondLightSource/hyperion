from typing import Iterator, List

from ophyd import Component, Device, EpicsSignal, StatusBase
from ophyd.status import SubscriptionStatus

from functools import partial, partialmethod

PC_DIR_POS = 0
PC_DIR_NEG = 1

PC_ARM_SOURCE_SOFT = 0
PC_ARM_SOURCE_EXT = 1

PC_GATE_SOURCE_POSITION = 0
PC_GATE_SOURCE_TIME = 1
PC_GATE_SOURCE_EXTERNAL = 2

PC_PULSE_SOURCE_POSITION = 0
PC_PULSE_SOURCE_TIME = 1
PC_PULSE_SOURCE_EXTERNAL = 2

# Sources
DISCONNECT = 0
IN1_TTL = 1
IN2_TTL = 4
PC_ARM = 29
PC_GATE = 30
PC_PULSE = 31
AND3 = 34
AND4 = 35
OR1 = 36
PULSE1 = 52
SOFT_IN3 = 62

PULSE_TIMEUNIT_10SEC = 2
PULSE_TIMEUNIT_SEC = 1
PULSE_TIMEUNIT_MS = 0

class CaptureInput(Device):
	enc1: EpicsSignal = Component(EpicsSignal, "B0")
	enc2: EpicsSignal = Component(EpicsSignal, "B1")
	enc3: EpicsSignal = Component(EpicsSignal, "B2")
	enc4: EpicsSignal = Component(EpicsSignal, "B3")


class PositionCompare(Device):
	capture_input: CaptureInput = Component(CaptureInput, "PC_BIT_CAP:")
	trigger_encoder: EpicsSignal = Component(EpicsSignal, "PC_ENC")

	gate_start: EpicsSignal = Component(EpicsSignal, "PC_GATE_START")
	gate_width: EpicsSignal = Component(EpicsSignal, "PC_GATE_WID")
	num_gates: EpicsSignal = Component(EpicsSignal, "PC_GATE_NGATE")
	gate_step: EpicsSignal = Component(EpicsSignal, "PC_GATE_STEP")
	gate_source: EpicsSignal = Component(EpicsSignal, "PC_GATE_SEL")
	gate_input: EpicsSignal = Component(EpicsSignal, "PC_GATE_INP")

	pulse_source: EpicsSignal = Component(EpicsSignal, "PC_PULSE_SEL")
	pulse_start: EpicsSignal = Component(EpicsSignal, "PC_PULSE_START")
	pulse_width: EpicsSignal = Component(EpicsSignal, "PC_PULSE_WID")
	max_pulses: EpicsSignal = Component(EpicsSignal, "PC_PULSE_MAX")
	pulse_step: EpicsSignal = Component(EpicsSignal, "PC_PULSE_STEP")
	pulse_delay: EpicsSignal = Component(EpicsSignal, "PC_PULSE_DLY")
	pulse_input: EpicsSignal = Component(EpicsSignal, "PC_PULSE_INP")

	dir: EpicsSignal = Component(EpicsSignal, "PC_DIR")
	arm_source: EpicsSignal = Component(EpicsSignal, "PC_ARM_SEL")
	arm_demand: EpicsSignal = Component(EpicsSignal, "PC_ARM")
	disarm_demand: EpicsSignal = Component(EpicsSignal, "PC_DISARM")
	armed: EpicsSignal = Component(EpicsSignal, "PC_ARM_OUT")

	def setup_fast_grid_scan(self):
		#TODO: Does it make sense to wait on all of these?
		self.arm_source.put(PC_ARM_SOURCE_SOFT).wait(1.0)
		self.gate_source.put(PC_GATE_SOURCE_EXTERNAL).wait(1.0)

		# Set up parameters for the GATE
		self.gate_input.put(SOFT_IN3).wait(1.0)
		self.num_gates.put(1).wait(1.0)

		# Pulses come in through TTL input 1
		self.pulse_source.put(PC_PULSE_SOURCE_EXTERNAL).wait(1.0)
		self.pulse_input.put(IN1_TTL).wait(1.0)
		return super().stage()

	def unstage(self) -> List[object]:
		self.disarm().wait(10.0)
		return super().unstage()

	def arm(self) -> StatusBase:
		status = self.arm_status(1)
		self.arm_demand.put(1)
		return status

	def disarm(self) -> StatusBase:
		status = self.arm_status(0)
		self.disarm_demand.put(1)
		return status

	def is_armed(self) -> bool:
		return self.armed.get() == 1

	def arm_status(self, armed: int) -> StatusBase:
		return SubscriptionStatus(self.armed, lambda value, **_: value == armed)


class ZebraOutputPanel(Device):
	# TODO: Need to check these (also instrument dependent not Device so shouldn't live here)
	DETECTOR_TTL = 2 
	TTL_SHUTTER = 4 
	TTL_XSPRESS3 = 3

	pulse_1_input: EpicsSignal = Component(EpicsSignal, "PULSE1_INP")
	pulse_1_delay: EpicsSignal = Component(EpicsSignal, "PULSE1_DLY")
	pulse_1_width: EpicsSignal = Component(EpicsSignal, "PULSE1_WID")
	pulse_1_time_units: EpicsSignal = Component(EpicsSignal, "PULSE1_PRE")

	def __init__(self) -> None:
		self.out_pvs = [Component(EpicsSignal, f"OUT{out_i}_TTL") for out_i in range(1, 5)]

	def setup_fast_grid_scan(self):
		self.out_pvs[self.DETECTOR_TTL].put(AND3).wait(1.0)
		self.out_pvs[self.TTL_SHUTTER].put(AND4).wait(1.0)
		self.out_pvs[self.TTL_XSPRESS3].put(DISCONNECT).wait(1.0)
	
	def enable_fluo_collection(self, fluo_exposure_time: float):
		# Generate a pulse, triggered immediately when IN1_TTL goes high
		self.pulse_1_input.put(IN1_TTL).wait(1.0)
		self.pulse_1_delay.put(0.0).wait(1)

		# Pulse width is the specified exposure time
		self.pulse_1_width.put(fluo_exposure_time).wait(1)
		self.pulse_1_time_units.put(PULSE_TIMEUNIT_SEC).wait(1)

		# Pulse should go out to the Xspress 3
		self.out_pvs[self.TL_XSPRESS3].put(PULSE1).wait(1)
	
	def disable_fluo_collection(self):
		# No PULSE1
		self.pulse_1_input.put(DISCONNECT).wait(1)

		# No signal out to the Xspress 3
		self.out_pvs[self.TTL_XSPRESS3].put(DISCONNECT).wait(1.0)

	def set_shutter_to_manual(self):
		self.out_pvs[self.DETECTOR_TTL].put(PC_GATE).wait(1.0)
		self.out_pvs[self.TTL_SHUTTER].put(OR1).wait(1.0)


# TODO: More pythonic way to do this
def boolean_array_to_integer(values : List[bool]) -> int:
	val = 0
	for i, value in enumerate(values):
		if (value):
			val += (1 << i)
	return val

class LogicGateConfigurer(Device):
	NUMBER_OF_GATES = 4

	def gate_enable_pv(gate_type: int, gate_number: int) -> Component: 
		return Component(EpicsSignal, f"{gate_type}{gate_number}_ENA")

	def gate_source_pv(gate_type: str, gate_number: int, gate_input: int) -> Component: 
		return Component(EpicsSignal, f"{gate_type}{gate_number}_INP{gate_input}")

	def gate_invert_pv(gate_type: str, gate_number: int) -> Component: 
		return Component(EpicsSignal, f"{gate_type}{gate_number}_INV")

	def apply_logic_gate_config(self, type : str, gateNumber : int, config):
		use_pv = self.gate_enable_pv(type, gateNumber)
		use_pv.put(boolean_array_to_integer(config.get_use()))

		# Input Source
		for input in range(1, self.NUMBER_OF_GATES + 1):
			source_pv = self.gate_source_pv(type, gateNumber, input)
			source_pv.put(config.getSources()[input - 1])

		# Invert
		invert_pv = self.gate_invert_pv(type, gateNumber)
		invert_pv.put(boolean_array_to_integer(config.getInvert()))

	apply_and_gate_config = partialmethod(apply_logic_gate_config, "AND")
	apply_or_gate_config = partialmethod(apply_logic_gate_config, "OR")

	def setup_fast_grid_scan(self):
		# Set up AND3 block - produces trigger when SOFT_IN3 is high, AND a pulse is received from Geo Brick (via IN1_TTL)
		and3_config = LogicGateConfiguration(1, PC_ARM).add_gate(2, IN1_TTL)
		self.apply_and_gate_config(3, and3_config)

		# Set up AND4 block - produces trigger when SOFT_IN3 is high, AND a pulse is received from Geo Brick (via IN2_TTL)
		and4_config = LogicGateConfiguration(1, PC_ARM).add_gate(2, IN2_TTL)
		self.apply_and_gate_config(4, and4_config)

class LogicGateConfiguration():
	NUMBER_OF_GATES = 4

	use = [False] * NUMBER_OF_GATES
	sources = [0] * NUMBER_OF_GATES
	invert = [False] * NUMBER_OF_GATES

	def __init__(self, use_gate: int, input_source: int, invert: bool = False) -> None:
		self.add_gate(use_gate, input_source, invert)

	def add_gate(self, use_gate: int, input_source: int, invert: bool = False) -> None:
		assert 1 <= use_gate <= self.NUMBER_OF_GATES
		assert 0 <= input_source <= 63 
		self.use[use_gate - 1] = True
		self.input_source[use_gate - 1] = input_source
		self.invert[use_gate - 1] = invert

	def __str__(self) -> str:
		bits = []
		for (input, use, source, invert) in enumerate(zip(self.use, self.sources, self.invert)):
			if use:
				bits.append(f"INP{input+1}={'!' if invert else ''}{source}")

		return str(bits)

class Zebra(Device):
	pc: PositionCompare = Component(PositionCompare, "")
	output: ZebraOutputPanel = Component(ZebraOutputPanel, "")
	logic_gates: LogicGateConfigurer = Component(LogicGateConfigurer, "")

	collecting_fluo_data = True
	fluo_exposure_time = 0.1

	def setup_fast_grid_scan(self):
		self.pc.setup_fast_grid_scan()
		self.logic_gates.setup_fast_grid_scan()
		self.output.setup_fast_grid_scan()
	
	def stage(self) -> List[object]:
		self.setup_fast_grid_scan()

		if self.collecting_fluo_data:
			self.output.enable_fluo_collection(self.fluo_exposure_time)
		else:
			self.output.disable_fluo_collection()
		
		self.pc.arm()

	def unstage(self) -> List[object]:
		self.pc.disarm()
		if self.collecting_fluo_data:
			self.output.disable_fluo_collection()
		self.output.set_shutter_to_manual()
		
