from abc import abstractmethod


class BaseExperimentParameters:
    num_images: float

    @abstractmethod
    def get_num_images(self):
        raise NotImplementedError
