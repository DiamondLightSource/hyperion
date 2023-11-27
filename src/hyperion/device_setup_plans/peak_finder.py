from abc import ABC, abstractmethod

from bluesky import plan_stubs as bps
from bluesky import preprocessors as bpp
from bluesky.plans import scan
from numpy import argmax
from ophyd import EpicsMotor, EpicsSignalRO

from hyperion.log import LOGGER


class PeakFinder(ABC):
    """Generates a bluesky plan to find a peak
    Args:
        x: independent variable e.g. motor to adjust
        y: dependent variable e.g. intensity monitor
        centre: estimated centre of peak to find
        width: estimated width of peak to find
        step: scan step
    Returns:
        The x-coordinate of the located peak
    """

    @abstractmethod
    def find_peak_plan(self, x: EpicsMotor, y: EpicsSignalRO, centre, width, step):
        pass


class PeakEstimator(ABC):
    """Estimates a peak location given a set of data
    Args: list of (x, y) tuples
    Returns: the x coordinate"""

    @abstractmethod
    def estimate_peak(self, data: list[tuple[float, float]]):
        pass


class SingleScanPassPeakFinder(PeakFinder):
    """Finds a peak by performing a once-through pass, then finding the peak in the returned data.
    Moves the motor to the located peak."""

    def __init__(self, peak_estimator: PeakEstimator):
        self._peak_estimator = peak_estimator

    def find_peak_plan(self, x: EpicsMotor, y: EpicsSignalRO, centre, width, step):
        xy_data = []

        def handle_event(name, doc):
            LOGGER.debug(f"Got {name} document {doc}")
            if name == "descriptor":
                pass
            elif name == "event":
                data = doc.get("data")
                y_name = y.name
                x_name = x.name + "_user_setpoint"
                if data and x_name in data and y_name in data:
                    data_point = (data.get(x_name), data.get(y_name))
                    LOGGER.debug(f"Got data_point={data_point}")
                    xy_data.append(data_point)

        def read_data(detectors, step, pos_cache):
            yield from bps.move_per_step(step, pos_cache)
            yield from bps.create()
            try:
                yield from bps.rd(x.user_setpoint)
                yield from bps.rd(y)
                yield from bps.save()
            except Exception as e:
                yield from bps.drop()
                raise e

        num_steps = int(2 * width / step + 1)
        yield from bpp.subs_wrapper(
            scan(
                [y],
                x,
                centre - width,
                centre + width,
                num=num_steps,
                per_step=read_data,
            ),
            handle_event,
        )

        estimated_peak_x = self._peak_estimator.estimate_peak(xy_data)
        yield from bps.mv(x, estimated_peak_x, wait=True)
        return estimated_peak_x


class SimpleMaximumPeakEstimator(PeakEstimator):
    """Just returns the x-coordinate of the maximum value in the data set"""

    def estimate_peak(self, data):
        i_max = argmax([y for x, y in data])
        return data[i_max][0]
