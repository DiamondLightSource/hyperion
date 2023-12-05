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
        """A callback base class which can be left permanently subscribed to a plan, and
        will 'activate' and 'deactivate' at the start and end of a plan which provides
        metadata to trigger this.
        The run_decorator of the plan should include in its metadata dictionary the key
        'activate callbacks', with a list of strings of the callback class(es) to
        activate or deactivate. On a recieving a start doc which specifies this, this
        class will be activated, and on recieving the stop document for the
        corresponding uid it will deactivate. The ordinary 'start', 'descriptor',
        'event' and 'stop' methods will be triggered as normal, and will in turn trigger
        'activity_gated_' methods - to preserve this functionality, subclasses which
        override 'start' etc. should include a call to super().start(...) etc.
        The logic of how activation is triggered will change to a more readable, version
        in the future (https://github.com/DiamondLightSource/hyperion/issues/964)."""
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

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} with id: {hex(id(self))}>"
