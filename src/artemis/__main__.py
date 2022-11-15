import argparse
import atexit
import threading
from dataclasses import dataclass
from enum import Enum
from json import JSONDecodeError
from queue import Queue
from typing import Optional, Tuple

from bluesky import RunEngine
from dataclasses_json import dataclass_json
from flask import Flask, request
from flask_restful import Api, Resource

import artemis.log
from artemis.external_interaction.communicator_callbacks import (
    FGSCallbackCollection,
    FGSCommunicator,
    NexusFileHandlerCallback,
)
from artemis.fast_grid_scan_plan import get_plan
from artemis.parameters import FullParameters


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
    parameters: Optional[FullParameters] = None


@dataclass_json
@dataclass
class StatusAndMessage:
    status: str
    message: str = ""

    def __init__(self, status: Status, message: str = "") -> None:
        self.status = status.value
        self.message = message


class BlueskyRunner:
    callbacks: FGSCallbackCollection
    command_queue: "Queue[Command]" = Queue()
    current_status: StatusAndMessage = StatusAndMessage(Status.IDLE)
    last_run_aborted: bool = False

    def __init__(self, RE: RunEngine) -> None:
        self.callbacks = FGSCallbackCollection()
        self.RE = RE

    def start(self, parameters: FullParameters) -> StatusAndMessage:
        artemis.log.LOGGER.info(f"Started with parameters: {parameters}")
        self.callbacks.fgs_communicator = FGSCommunicator(parameters)
        self.callbacks.nexus_handler = NexusFileHandlerCallback(parameters)
        if (
            self.current_status.status == Status.BUSY.value
            or self.current_status.status == Status.ABORTING.value
        ):
            return StatusAndMessage(Status.FAILED, "Bluesky already running")
        else:
            self.current_status = StatusAndMessage(Status.BUSY)
            self.command_queue.put(Command(Actions.START, parameters))
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
                    self.RE(get_plan(command.parameters, self.callbacks))
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
                parameters = FullParameters.from_json(request.data)
                status_and_message = self.runner.start(parameters)
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
    return app, runner


def cli_arg_parse() -> Tuple[Optional[bool], Optional[str]]:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Use dev options, such as local graylog instances and S03",
    )
    parser.add_argument(
        "--logging-level",
        type=str,
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Choose overall logging level, defaults to INFO",
    )
    args = parser.parse_args()
    return args.logging_level, args.dev


if __name__ == "__main__":
    args = cli_arg_parse()
    artemis.log.set_up_logging_handlers(*args)
    app, runner = create_app()
    atexit.register(runner.shutdown)
    flask_thread = threading.Thread(
        target=lambda: app.run(
            host="0.0.0.0", port=5005, debug=True, use_reloader=False
        ),
        daemon=True,
    )
    flask_thread.start()
    runner.wait_on_queue()
    flask_thread.join()
