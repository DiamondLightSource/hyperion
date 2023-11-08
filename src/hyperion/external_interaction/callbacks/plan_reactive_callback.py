from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from bluesky.callbacks import CallbackBase
from event_model.documents.event import Event

if TYPE_CHECKING:
    from event_model.documents.event import Event
    from event_model.documents.event_descriptor import EventDescriptor
    from event_model.documents.run_start import RunStart
    from event_model.documents.run_stop import RunStop


class PlanReactiveCallback(CallbackBase):
    def __init__(self, *, emit: Callable[..., Any] | None = None) -> None:
        super().__init__(emit=emit)
        self.active = False
        self.activity_uid = 0

    def start(self, doc: RunStart) -> RunStart | None:
        callbacks_to_activate = doc.get("activate_callbacks")
        if callbacks_to_activate:
            self.active = type(self).__name__ in callbacks_to_activate
            self.activity_uid = doc.get("uid")
        return self.activity_gated_start(doc) if self.active else doc

    def descriptor(self, doc: EventDescriptor) -> EventDescriptor | None:
        return self.activity_gated_descriptor(doc) if self.active else doc

    def event(self, doc: Event) -> Event | None:
        return self.activity_gated_event(doc) if self.active else doc

    def stop(self, doc: RunStop) -> RunStop | None:
        do_stop = self.active
        if doc.get("run_start") == self.activity_uid:
            self.active = False
            self.activity_uid = 0
        return self.activity_gated_stop(doc) if do_stop else doc

    def activity_gated_start(self, doc: RunStart):
        return None

    def activity_gated_descriptor(self, doc: EventDescriptor):
        return None

    def activity_gated_event(self, doc: Event):
        return None

    def activity_gated_stop(self, doc: RunStop):
        return None
