import numpy as np


class Point3D(np.ndarray):
    def __new__(self, x: float, y: float, z: float):
        a = super().__new__(Point3D, shape=3, dtype=float)
        a.x = a[0] = x
        a.y = a[1] = y
        a.z = a[2] = z
        return a

    def __array_finalize__(self, a):
        if a is None:
            return
        self.x = self[0]
        self.y = self[1]
        self.z = self[2]


class Point2D(np.ndarray):
    def __new__(self, x: float, y: float, z: float):
        a = super().__new__(Point2D, shape=2, dtype=float)
        a.x = a[0] = x
        a.y = a[1] = y
        return a

    def __array_finalize__(self, a):
        if a is None:
            return
        self.x = self[0]
        self.y = self[1]
