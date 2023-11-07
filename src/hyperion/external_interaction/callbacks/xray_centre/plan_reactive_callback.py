from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from bluesky.callbacks import CallbackBase

if TYPE_CHECKING:
    from event_model.documents.event import Event
    from event_model.documents.event_descriptor import EventDescriptor
    from event_model.documents.run_start import RunStart
    from event_model.documents.run_stop import RunStop


class PlanReactiveCallback(CallbackBase):
    def __init__(self, *, emit: Callable[..., Any] | None = None) -> None:
        super().__init__(emit=emit)
        self.active = False

    def start(self, doc: RunStart) -> RunStart | None:
        callbacks_to_activate = doc.get("activate_callbacks") or []
        if type(self) in callbacks_to_activate:
            self.active = True
        if self.active:
            return self.activity_gated_start(doc)
        return None

    def descriptor(self, doc: EventDescriptor) -> EventDescriptor | None:
        if self.active:
            return self.activity_gated_descriptor(doc)
        return None

    def event(self, doc: Event) -> Event | None:
        if self.active:
            return self.activity_gated_event(doc)
        return None

    def stop(self, doc: RunStop) -> RunStop | None:
        if self.active:
            return self.activity_gated_stop(doc)
        return None

    def activity_gated_start(self, doc: RunStart):
        return NotImplemented

    def activity_gated_descriptor(self, doc: EventDescriptor):
        return NotImplemented

    def activity_gated_event(self, doc: Event):
        return NotImplemented

    def activity_gated_stop(self, doc: RunStop):
        return NotImplemented
