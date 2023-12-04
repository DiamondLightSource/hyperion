from abc import ABC, abstractmethod
from math import cos

import numpy as np
from numpy import interp, loadtxt

from hyperion.log import LOGGER


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

        # numpy interp expects x-values to be increasing
        if not np.all(np.diff(self._s_values) > 0):
            LOGGER.info(
                f"Configuration file {filename} values are not ascending, trying reverse order..."
            )
            self._s_values = list(reversed(self._s_values))
            self._t_values = list(reversed(self._t_values))
            if not np.all(np.diff(self._s_values) > 0):
                LOGGER.error(
                    f"Configuration file {filename} lookup table does not monotonically increase or decrease."
                )
                raise AssertionError(
                    f"Configuration file {filename} lookup table does not monotonically increase or decrease."
                )

    def s_to_t(self, s):
        # XXX numpy.interp doesn't do extrapolation, whereas GDA does, do we need this?
        return interp(s, self._s_values, self._t_values)


class PerpRollLUTConverter(LookupTableConverter):
    # TODO if we need to read the XML JEPQuantityConverter file instead of hardcoding this
    def s_to_t(self, s):
        return -1.0 * (25 / (2.0 * cos(s * 3.1416 / 180.0)) - 13.56)


# class DiscontinuousLinearInterpolation(LookupTableConverter):
#     """Linearly interpolate between pairs of (s, t) points in the lookup table. Where the LUT provides two points for
#      the same s-coordinate, the first point provides the control point to be paired with preceding point and the second
#      with the succeeding point."""
#     def __init__(self, filename: str):
#         super().__init__()
#         s_and_t_vals = zip(*loadtxt(filename, comments=["#", "Units"]))
#         self._s_values, self._t_values = s_and_t_vals
#
#     def s_to_t(self, s):
#
#         return interp(s, self._s_values, self._t_values)
