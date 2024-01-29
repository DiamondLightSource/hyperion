from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import fields
from typing import Any, Generator

from bluesky.callbacks import CallbackBase


class AbstractPlanCallbackCollection(ABC):
    """Base class for a collection of callbacks to attach to a plan. Subclasses should
    also be dataclasses, or override __iter__. In general, you should use
    '@dataclass(frozen=True, order=True)' for your subclass, in which case you can use
    @subs_decorator(list(callback_collection)) to subscribe them to your plan in order.
    """

    @classmethod
    @abstractmethod
    def setup(cls) -> AbstractPlanCallbackCollection:
        ...

    def __iter__(self) -> Generator[CallbackBase, Any, None]:
        for field in fields(self):  # type: ignore # subclasses must be dataclass
            yield getattr(self, field.name)


class NullPlanCallbackCollection(AbstractPlanCallbackCollection):
    @classmethod
    def setup(cls):
        return cls()

    def __iter__(self):
        yield from ()
