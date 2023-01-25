from abc import abstractmethod


class BaseExperimentDeviceParameters:
    """
    Subclass this for parameter sets for composite devices for experiments, e.g.
    fast_grid_scan or rotation_scan. Defines methods which should be available on any
    of these without having been specified in external parameters, such as the number
    of images.
    """

    num_images: float

    @abstractmethod
    def get_num_images(self):
        raise NotImplementedError
