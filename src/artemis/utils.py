from collections import namedtuple

import numpy as np


def create_point(*args):
    if len(args) == 2:
        return np.array([args[0], args[1]], dtype=np.int8)
    elif len(args) == 3:
        return np.array([args[0], args[1], args[2]], dtype=np.int8)
    else:
        raise AttributeError("test")


Point2D = namedtuple("Point2D", ["x", "y"])
Point3D = namedtuple("Point3D", ["x", "y", "z"])
