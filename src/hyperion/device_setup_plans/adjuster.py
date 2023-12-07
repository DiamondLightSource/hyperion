from abc import ABC, abstractmethod
from typing import Generator

from bluesky import Msg
from bluesky import plan_stubs as bps
from ophyd import EpicsMotor

from hyperion.log import LOGGER
from hyperion.utils.lookup_table import LookupTableConverter


class Adjuster(ABC):
    """Abstraction that adjusts a value according to some criteria either via feedback, preset positions, lookup tables etc."""

    @abstractmethod
    def adjust(self, group=None) -> Generator[Msg, None, None]:
        pass


class NullAdjuster(Adjuster):
    def adjust(self, group=None) -> Generator[Msg, None, None]:
        pass


class LUTAdjuster(Adjuster):
    def __init__(
        self, lookup_table: LookupTableConverter, output_device: EpicsMotor, input
    ):
        self._lookup_table = lookup_table
        self._input = input
        self._output_device = output_device

    """Adjusts a value according to a lookup table"""

    def adjust(self, group=None) -> Generator[Msg, None, None]:
        setpoint = self._lookup_table.s_to_t(self._input)
        LOGGER.info(f"LUTAdjuster Setting {self._output_device.name} to {setpoint}")
        yield from bps.abs_set(self._output_device, setpoint, group=group)
