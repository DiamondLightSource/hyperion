from abc import abstractmethod


class BaseExperimentParameters:
    @abstractmethod
    def get_num_images(self):
        raise NotImplementedError
