from __future__ import annotations

from logging import Logger
from typing import TYPE_CHECKING, Any, Callable

from bluesky.callbacks import CallbackBase

if TYPE_CHECKING:
    from event_model.documents.event import Event
    from event_model.documents.event_descriptor import EventDescriptor
    from event_model.documents.run_start import RunStart
    from event_model.documents.run_stop import RunStop


class PlanReactiveCallback(CallbackBase):
    def __init__(
        self, *, emit: Callable[..., Any] | None = None, log: Logger | None = None
    ) -> None:
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
        self.log = log  # type: ignore # this is initialised to None and not annotated in the superclass

    def _run_activity_gated(self, func, doc):
        if not self.active:
            return doc
        if self.log:
            try:
                return func(doc) if self.active else doc
            except Exception as e:
                self.log.exception(e)
                raise
        else:
            return func(doc) if self.active else doc

    def start(self, doc: RunStart) -> RunStart | None:
        callbacks_to_activate = doc.get("activate_callbacks")
        if callbacks_to_activate:
            activate = type(self).__name__ in callbacks_to_activate
            self.active = activate
            self.optional_info_log(
                f"{'' if activate else 'not'} activating {type(self).__name__}"
            )
            self.activity_uid = doc.get("uid")
        return self._run_activity_gated(self.activity_gated_start, doc)

    def descriptor(self, doc: EventDescriptor) -> EventDescriptor | None:
        return self._run_activity_gated(self.activity_gated_descriptor, doc)

    def event(self, doc: Event) -> Event | None:
        return self._run_activity_gated(self.activity_gated_event, doc)

    def stop(self, doc: RunStop) -> RunStop | None:
        do_stop = self.active
        if doc.get("run_start") == self.activity_uid:
            self.active = False
            self.activity_uid = 0
        return (
            self._run_activity_gated(self.activity_gated_stop, doc) if do_stop else doc
        )

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

    def optional_info_log(self, msg):
        if self.log:
            self.log.info(msg)

    def optional_debug_log(self, msg):
        if self.log:
            self.log.debug(msg)
