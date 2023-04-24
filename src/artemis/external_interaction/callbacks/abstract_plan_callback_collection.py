from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import fields
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from artemis.parameters.internal_parameters.internal_parameters import (
        InternalParameters,
    )


class AbstractPlanCallbackCollection(ABC):
    """Base class for a collection of callbacks to attach to a plan. Subclasses should
    also be dataclasses, or override __iter__"""

    @classmethod
    @abstractmethod
    def from_params(cls, params: InternalParameters):
        ...

    def __iter__(self):
        for field in fields(self):
            yield getattr(self, field.name)
