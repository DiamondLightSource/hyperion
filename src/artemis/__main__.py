import atexit
import logging
import threading
from dataclasses import dataclass
from enum import Enum
from json import JSONDecodeError
from queue import Queue
from typing import Any, Generator, Optional, Tuple

from bluesky import RunEngine
from bluesky.suspenders import SuspendBoolHigh
from dataclasses_json import dataclass_json
from flask import Flask, request
from flask_restful import Api, Resource

from artemis.beam_topup_plan import dummy_plan, get_synchrotron_monitor_from_parameters
from artemis.fast_grid_scan_plan import get_plan
from artemis.parameters import FullParameters
from artemis.topup_parameters import TopupParameters

logger = logging.getLogger(__name__)


class Actions(Enum):
    START = "start"
    STOP = "stop"
    SHUTDOWN = "shutdown"


class Status(Enum):
    FAILED = "Failed"
    SUCCESS = "Success"
    BUSY = "Busy"
    ABORTING = "Aborting"
    IDLE = "Idle"


@dataclass
class Command:
    action: Actions
    plan: Optional[Generator] = None
    plan_parameters: Optional[Any] = None


@dataclass_json
@dataclass
class StatusAndMessage:
    status: str
    message: str = ""

    def __init__(self, status: Status, message: str = "") -> None:
        self.status = status.value
        self.message = message


class BlueskyRunner:
    command_queue: "Queue[Command]" = Queue()
    current_status: StatusAndMessage = StatusAndMessage(Status.IDLE)
    last_run_aborted: bool = False

    def __init__(self, RE: RunEngine) -> None:
        self.RE = RE

    def start(self, plan: Generator, parameters: FullParameters) -> StatusAndMessage:
        logger.info(f"Started with parameters: {parameters}")
        if (
            self.current_status.status == Status.BUSY.value
            or self.current_status.status == Status.ABORTING.value
        ):
            return StatusAndMessage(Status.FAILED, "Bluesky already running")
        else:
            self.current_status = StatusAndMessage(Status.BUSY)
            self.command_queue.put(Command(Actions.START, plan, parameters))
            return StatusAndMessage(Status.SUCCESS)

    def stopping_thread(self):
        try:
            self.RE.abort()
            self.current_status = StatusAndMessage(Status.IDLE)
        except Exception as e:
            self.current_status = StatusAndMessage(Status.FAILED, str(e))

    def stop(self) -> StatusAndMessage:
        if self.current_status.status == Status.IDLE.value:
            return StatusAndMessage(Status.FAILED, "Bluesky not running")
        elif self.current_status.status == Status.ABORTING.value:
            return StatusAndMessage(Status.FAILED, "Bluesky already stopping")
        else:
            self.current_status = StatusAndMessage(Status.ABORTING)
            stopping_thread = threading.Thread(target=self.stopping_thread)
            stopping_thread.start()
            self.last_run_aborted = True
            return StatusAndMessage(Status.ABORTING)

    def shutdown(self):
        """Stops the run engine and the loop waiting for messages."""
        print("Shutting down: Stopping the run engine gracefully")
        self.stop()
        self.command_queue.put(Command(Actions.SHUTDOWN))

    def wait_on_queue(self):
        while True:
            command = self.command_queue.get()
            if command.action == Actions.START:
                try:
                    self.RE(command.plan(command.plan_parameters))
                    self.current_status = StatusAndMessage(Status.IDLE)
                    self.last_run_aborted = False
                except Exception as exception:
                    if self.last_run_aborted:
                        # Aborting will cause an exception here that we want to swallow
                        self.last_run_aborted = False
                    else:
                        self.current_status = StatusAndMessage(
                            Status.FAILED, str(exception)
                        )
            elif command.action == Actions.SHUTDOWN:
                return


class FastGridScan(Resource):
    def __init__(self, runner: BlueskyRunner) -> None:
        super().__init__()
        self.runner = runner

    def put(self, action):
        status_and_message = StatusAndMessage(Status.FAILED, f"{action} not understood")
        if action == Actions.START.value:
            try:
                self.runner.RE.clear_suspenders()
                parameters = FullParameters.from_json(request.data)
                status_and_message = self.runner.start(get_plan, parameters)
            except JSONDecodeError as exception:
                status_and_message = StatusAndMessage(Status.FAILED, str(exception))
        elif action == Actions.STOP.value:
            status_and_message = self.runner.stop()
        return status_and_message.to_dict()

    def get(self, action):
        return self.runner.current_status.to_dict()


class Dummy(Resource):
    def __init__(self, runner: BlueskyRunner) -> None:
        super().__init__()
        self.runner = runner

    def put(self, action):
        status_and_message = StatusAndMessage(Status.FAILED, f"{action} not understood")
        if action == Actions.START.value:
            try:
                self.runner.RE.clear_suspenders()
                topup_plan_params = TopupParameters()
                topup_plan_params.total_exposure_time = 100
                topup_plan_params.instability_time = 45
                topup_plan_params.threshold_percentage = 10
                synchrotron_monitor = get_synchrotron_monitor_from_parameters(
                    topup_plan_params
                )
                sus = SuspendBoolHigh(synchrotron_monitor.topup_gate_signal)
                self.runner.RE.install_suspender(sus)
                status_and_message = self.runner.start(
                    dummy_plan,
                    synchrotron_monitor,
                )
            except JSONDecodeError as exception:
                status_and_message = StatusAndMessage(Status.FAILED, str(exception))
        elif action == Actions.STOP.value:
            status_and_message = self.runner.stop()
        return status_and_message.to_dict()

    def get(self, action):
        return self.runner.current_status.to_dict()


def create_app(
    test_config=None, RE: RunEngine = RunEngine({})
) -> Tuple[Flask, BlueskyRunner]:
    runner = BlueskyRunner(RE)
    app = Flask(__name__)
    if test_config:
        app.config.update(test_config)
    api = Api(app)
    api.add_resource(
        FastGridScan, "/fast_grid_scan/<string:action>", resource_class_args=[runner]
    )
    api.add_resource(Dummy, "/dummy/<string:action>", resource_class_args=[runner])
    return app, runner


if __name__ == "__main__":
    app, runner = create_app()
    atexit.register(runner.shutdown)
    flask_thread = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", debug=True, use_reloader=False),
        daemon=True,
    )
    flask_thread.start()
    runner.wait_on_queue()
    flask_thread.join()
