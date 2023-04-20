from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from artemis.parameters.internal_parameters.internal_parameters import (
        InternalParameters,
    )


class AbstractPlanCallbackCollection(ABC):
    @classmethod
    @abstractmethod
    def from_params(cls, params: InternalParameters):
        ...
