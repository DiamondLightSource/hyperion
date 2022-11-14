import numpy as np


class Point2D(np.ndarray):
    def __new__(cls, x: float, y: float):
        obj = super().__new__(cls, (2,), float, np.asarray((x, y)))
        obj.x = x
        obj.y = y
        return obj

    @property
    def x(self):
        return self[0]

    @x.setter
    def x(self, x):
        self[0] = x

    @property
    def y(self):
        return self[1]

    @y.setter
    def y(self, y):
        self[1] = y

    def __eq__(self, other):
        return np.all(self == other)

    def _asdict(self):
        return {"x": self.x, "y": self.y}


class Point3D(np.ndarray):
    def __new__(cls, x: float, y: float, z: float):
        obj = super().__new__(cls, (3,), float, np.asarray((x, y, z)))
        obj.x = x
        obj.y = y
        obj.z = z
        return obj

    @property
    def x(self):
        return self[0]

    @x.setter
    def x(self, x):
        self[0] = x

    @property
    def y(self):
        return self[1]

    @y.setter
    def y(self, y):
        self[1] = y

    @property
    def z(self):
        return self[2]

    @z.setter
    def z(self, z):
        self[2] = z

    def __eq__(self, other):
        return np.all(self == other)

    def _asdict(self):
        return {"x": self.x, "y": self.y, "z": self.z}
