"""
Module for containing errors in operation of the OAV.
"""

from artemis.log import LOGGER


class OAVError_ZoomLevelNotFound(Exception):
    def __init__(self, errmsg):
        LOGGER.error(errmsg)
