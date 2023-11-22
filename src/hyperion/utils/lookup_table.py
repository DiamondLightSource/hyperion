from abc import ABC, abstractmethod

from numpy import interp, loadtxt


class LookupTableConverter(ABC):
    """Interface for generic lookup table functionality."""

    @abstractmethod
    def s_to_t(self, s):
        pass


class LinearInterpolationLUTConverter(LookupTableConverter):
    def __init__(self, filename: str):
        super().__init__()
        s_and_t_vals = zip(*loadtxt(filename, comments=["#", "Units"]))
        self._s_values, self._t_values = s_and_t_vals

    def s_to_t(self, s):
        # XXX numpy.interp doesn't do extrapolation, whereas GDA does, do we need this?
        return interp(s, self._s_values, self._t_values)
