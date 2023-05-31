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
    also be dataclasses, or override __iter__. In general, you should use
    '@dataclass(frozen=True, order=True)' for your subclass, in which case you can use
    @subs_decorator(list(callback_collection)) to subscribe them to your plan in order.
    """

    @classmethod
    @abstractmethod
    def from_params(cls, params: InternalParameters):
        ...

    def __iter__(self):
        for field in fields(self):
            yield getattr(self, field.name)


class NullPlanCallbackCollection(AbstractPlanCallbackCollection):
    @classmethod
    def from_params(cls, params: InternalParameters):
        pass
