from functools import partial
from typing import Callable, Generator, Sequence
from unittest.mock import MagicMock, patch

import pytest
from bluesky.utils import Msg
from dodal.devices.fast_grid_scan import FastGridScan
from dodal.devices.zocalo import ZocaloResults, ZocaloTrigger
from event_model import Event
from ophyd.sim import make_fake_device
from ophyd_async.core.async_status import AsyncStatus

from hyperion.external_interaction.callbacks.rotation.callback_collection import (
    RotationCallbackCollection,
)
from hyperion.external_interaction.callbacks.xray_centre.callback_collection import (
    XrayCentreCallbackCollection,
)
from hyperion.external_interaction.callbacks.xray_centre.ispyb_callback import (
    GridscanISPyBCallback,
)
from hyperion.external_interaction.ispyb.store_datacollection_in_ispyb import (
    IspybIds,
    Store3DGridscanInIspyb,
)
from hyperion.log import LOGGER
from hyperion.parameters.constants import (
    GRIDSCAN_OUTER_PLAN,
    ISPYB_HARDWARE_READ_PLAN,
    ISPYB_TRANSMISSION_FLUX_READ_PLAN,
)
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)


def make_event_doc(data, descriptor="abc123") -> Event:
    return {
        "time": 0,
        "timestamps": {"a": 0},
        "seq_num": 0,
        "uid": "not so random uid",
        "descriptor": descriptor,
        "data": data,
    }


BASIC_PRE_SETUP_DOC = {
    "undulator_current_gap": 0,
    "undulator_gap": 0,
    "synchrotron_machine_status_synchrotron_mode": 0,
    "s4_slit_gaps_xgap": 0,
    "s4_slit_gaps_ygap": 0,
}
BASIC_POST_SETUP_DOC = {
    "attenuator_actual_transmission": 0,
    "flux_flux_reading": 10,
}


def mock_zocalo_trigger(zocalo: ZocaloResults, result):
    @AsyncStatus.wrap
    async def mock_complete(results):
        await zocalo._put_results(results)

    zocalo.trigger = MagicMock(side_effect=partial(mock_complete, result))


def run_generic_ispyb_handler_setup(
    ispyb_handler: GridscanISPyBCallback, params: GridscanInternalParameters
):
    """This is useful when testing 'run_gridscan_and_move(...)' because this stuff
    happens at the start of the outer plan."""

    ispyb_handler.active = True
    ispyb_handler.activity_gated_start(
        {
            "subplan_name": GRIDSCAN_OUTER_PLAN,
            "hyperion_internal_parameters": params.json(),
        }
    )
    ispyb_handler.activity_gated_descriptor(
        {"uid": "123abc", "name": ISPYB_HARDWARE_READ_PLAN}
    )
    ispyb_handler.activity_gated_event(
        make_event_doc(
            BASIC_PRE_SETUP_DOC,
            descriptor="123abc",
        )
    )
    ispyb_handler.activity_gated_descriptor(
        {"uid": "abc123", "name": ISPYB_TRANSMISSION_FLUX_READ_PLAN}
    )
    ispyb_handler.activity_gated_event(
        make_event_doc(
            BASIC_POST_SETUP_DOC,
            descriptor="abc123",
        )
    )


def modified_interactor_mock(assign_run_end: Callable | None = None):
    mock = MagicMock(spec=ZocaloTrigger)
    if assign_run_end:
        mock.run_end = assign_run_end
    return mock


def modified_store_grid_scan_mock(*args, dcids=(0, 0), dcgid=0, **kwargs):
    mock = MagicMock(spec=Store3DGridscanInIspyb)
    mock.begin_deposition.return_value = IspybIds(
        data_collection_ids=dcids, data_collection_group_id=dcgid, grid_ids=(0, 0)
    )
    return mock


@pytest.fixture
def mock_subscriptions(test_fgs_params):
    with patch(
        "hyperion.external_interaction.callbacks.xray_centre.zocalo_callback.ZocaloTrigger",
        modified_interactor_mock,
    ), patch(
        "hyperion.external_interaction.callbacks.xray_centre.ispyb_callback.Store3DGridscanInIspyb.append_to_comment"
    ):
        subscriptions = XrayCentreCallbackCollection.setup()
        start_doc = {
            "subplan_name": GRIDSCAN_OUTER_PLAN,
            "hyperion_internal_parameters": test_fgs_params.json(),
        }
        subscriptions.ispyb_handler.activity_gated_start(start_doc)
        subscriptions.zocalo_handler.activity_gated_start(start_doc)
    subscriptions.ispyb_handler.ispyb = MagicMock(spec=Store3DGridscanInIspyb)
    subscriptions.ispyb_handler.ispyb.begin_deposition = lambda: IspybIds(
        data_collection_ids=(0, 0), data_collection_group_id=0, grid_ids=(0, 0)
    )

    return subscriptions


@pytest.fixture
def mock_rotation_subscriptions(test_rotation_params):
    with patch(
        "hyperion.external_interaction.callbacks.rotation.callback_collection.RotationNexusFileCallback",
        autospec=True,
    ), patch(
        "hyperion.external_interaction.callbacks.rotation.callback_collection.RotationISPyBCallback",
        autospec=True,
    ), patch(
        "hyperion.external_interaction.callbacks.rotation.callback_collection.RotationZocaloCallback",
        autospec=True,
    ):
        subscriptions = RotationCallbackCollection.setup()
    return subscriptions


def fake_read(obj, initial_positions, _):
    initial_positions[obj] = 0
    yield Msg("null", obj)


@pytest.fixture
def simple_beamline(detector_motion, oav, smargon, synchrotron):
    magic_mock = MagicMock()
    magic_mock.oav = oav
    magic_mock.smargon = smargon
    magic_mock.detector_motion = detector_motion
    scan = make_fake_device(FastGridScan)("prefix", name="fake_fgs")
    magic_mock.fast_grid_scan = scan
    magic_mock.synchrotron = synchrotron
    oav.zoom_controller.frst.set("7.5x")
    return magic_mock


class MessageHandler:
    def __init__(self, p: Callable[[Msg], bool], r: Callable[[Msg], object]):
        self.predicate = p
        self.runnable = r


class RunEngineSimulator:
    """This class simulates a Bluesky RunEngine by recording and injecting responses to messages according to the
    bluesky Message Protocol (see bluesky docs for details).
    Basic usage consists of
    1) Registering various handlers to respond to anticipated messages in the experiment plan and fire any
    needed callbacks.
    2) Calling simulate_plan()
    3) Examining the returned message list and making asserts against them"""

    def __init__(self):
        self.message_handlers = []
        self.callbacks = {}
        self.next_callback_token = 0

    def add_handler_for_callback_subscribes(self):
        """Add a handler that registers all the callbacks from subscribe messages so we can call them later.
        You probably want to call this as one of the first things unless you have a good reason not to.
        """
        self.message_handlers.append(
            MessageHandler(
                lambda msg: msg.command == "subscribe",
                lambda msg: self._add_callback(msg.args),
            )
        )

    def add_handler(
        self, commands: Sequence[str], obj_name: str, handler: Callable[[Msg], object]
    ):
        """Add the specified handler for a particular message
        Args:
            commands: the command name for the message as defined in bluesky Message Protocol, or a sequence if more
            than one matches
            obj_name: the name property of the obj to match, can be None as not all messages have a name
            handler: a lambda that accepts a Msg and returns an object; the object is sent to the current yield statement
            in the generator, and is used when reading values from devices, the structure of the object depends on device
            hinting.
        """
        if isinstance(commands, str):
            commands = [commands]

        self.message_handlers.append(
            MessageHandler(
                lambda msg: msg.command in commands
                and (obj_name is None or (msg.obj and msg.obj.name == obj_name)),
                handler,
            )
        )

    def add_wait_handler(self, handler: Callable[[Msg], None], group: str = "any"):
        """Add a wait handler for a particular message
        Args:
            handler: a lambda that accepts a Msg, use this to execute any code that simulates something that's
            supposed to complete when a group finishes
            group: name of the group to wait for, default is any which matches them all
        """
        self.message_handlers.append(
            MessageHandler(
                lambda msg: msg.command == "wait"
                and (group == "any" or msg.kwargs["group"] == group),
                handler,
            )
        )

    def fire_callback(self, document_name, document):
        """Fire all the callbacks registered for this document type in order to simulate something happening
        Args:
             document_name: document name as defined in the Bluesky Message Protocol 'subscribe' call,
             all subscribers filtering on this document name will be called
             document: the document to send
        """
        for callback_func, callback_docname in self.callbacks.values():
            if callback_docname == "all" or callback_docname == document_name:
                callback_func(document_name, document)

    def simulate_plan(self, gen: Generator[Msg, object, object]) -> list[Msg]:
        """Simulate the RunEngine executing the plan
        Args:
            gen: the generator function that executes the plan
        Returns:
            a list of the messages generated by the plan
        """
        messages = []
        send_value = None
        try:
            while msg := gen.send(send_value):
                send_value = None
                messages.append(msg)
                LOGGER.debug(f"<{msg}")
                if handler := next(
                    (h for h in self.message_handlers if h.predicate(msg)), None
                ):
                    send_value = handler.runnable(msg)

                if send_value:
                    LOGGER.debug(f">send {send_value}")
        except StopIteration:
            pass
        return messages

    def _add_callback(self, msg_args):
        self.callbacks[self.next_callback_token] = msg_args
        self.next_callback_token += 1


def add_simple_pin_tip_centre_handlers(sim: RunEngineSimulator):
    """Handlers to simulate a basic fake pin tip"""
    sim.add_handler(
        ("trigger", "read"),
        "oav_mxsc_pin_tip",
        lambda msg: {"oav_mxsc_pin_tip_triggered_tip": {"value": (100, 100)}},
    )
    sim.add_handler(
        "read",
        "oav_mxsc_top",
        lambda msg: {"values": {"value": [50, 51, 52, 53, 54, 55]}},
    )
    sim.add_handler(
        "read",
        "oav_mxsc_bottom",
        lambda msg: {"values": {"value": [50, 49, 48, 47, 46, 45]}},
    )


def add_simple_oav_mxsc_callback_handlers(sim: RunEngineSimulator):
    """Handlers to simulate a basic oav callback firing"""
    sim.add_handler(
        "set",
        "oav_mxsc_enable_callbacks",
        # XXX what are reasonable values for these?
        lambda msg: sim.fire_callback(
            "event",
            {
                "data": {
                    "oav_snapshot_last_saved_path": "/tmp/image1.png",
                    "oav_snapshot_last_path_outer": "/tmp/image2.png",
                    "oav_snapshot_last_path_full_overlay": "/tmp/image3.png",
                    "oav_snapshot_top_left_x": 0,
                    "oav_snapshot_top_left_y": 0,
                    "oav_snapshot_box_width": 100,
                    "smargon_omega": 1,
                    "smargon_x": 0,
                    "smargon_y": 0,
                    "smargon_z": 0,
                    "oav_snapshot_num_boxes_x": 10,
                    "oav_snapshot_num_boxes_y": 10,
                }
            },
        ),
    )


def assert_message_and_return_remaining(messages: list, predicate):
    """Find the next message matching the predicate, assert that we found it
    Return: all the remaining messages starting from the matched message"""
    indices = [i for i in range(len(messages)) if predicate(messages[i])]
    assert indices, f"Nothing matched predicate {predicate}"
    return messages[indices[0] :]
