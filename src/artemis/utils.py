import numpy as np


def create_point(*args):
    args = list(args)
    for index, arg in enumerate(args):
        if args[index] is None:
            args[index] = 0

    if len(args) == 2:
        return np.array([args[0], args[1]], dtype=np.float16)
    elif len(args) == 3:
        return np.array([args[0], args[1], args[2]], dtype=np.float16)
    else:
        raise TypeError("Invalid number of arguments")
