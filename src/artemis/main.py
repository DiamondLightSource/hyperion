import os
import sys


sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from dataclasses import dataclass
from flask import Flask, request, globals
from flask_restful import Resource, Api
import logging
import threading
from json import JSONDecodeError
from queue import Queue
from typing import Optional
from bluesky import RunEngine
from bluesky.run_engine import RunEngineResult
from typing import Tuple
from enum import Enum
from src.artemis.fast_grid_scan_plan import FullParameters, get_plan
from dataclasses_json import dataclass_json


logger = logging.getLogger(__name__)


class Actions(Enum):
    START = "start"
    STOP = "stop"
    SHUTDOWN = "shutdown"


class Status(Enum):
    FAILED = "Failed"
    SUCCESS = "Success"
    BUSY = "Busy"
    IDLE = "Idle"


@dataclass
class Command:
    action: Actions
    parameters: Optional[FullParameters] = None


@dataclass_json
@dataclass
class StatusAndError:
    status: str
    message: str = ""

    def __init__(self, status: Status, message: str = "") -> None:
        self.status = status.value
        self.message = message


class BlueskyRunner(object):
    command_queue: "Queue[Command]" = Queue()
    RE: RunEngine = RunEngine({}, call_returns_result=True)
    last_RE_result: RunEngineResult = None
    RE_running: bool = False  # Keep track of this ourselves rather than ask the RE as it takes some time to start

    def start(self, parameters: FullParameters) -> StatusAndError:
        logger.info(f"Started with parameters: {parameters}")
        if self.RE_running:
            return StatusAndError(Status.FAILED, "Bluesky already running")
        else:
            self.RE_running = True
            self.command_queue.put(Command(Actions.START, parameters))
            return StatusAndError(Status.SUCCESS)

    def stop(self) -> StatusAndError:
        if not self.RE_running:
            return StatusAndError(Status.FAILED, "Bluesky not running")
        else:
            self.last_RE_result = self.RE.abort()
            self.RE_running = False
            return StatusAndError(Status.SUCCESS)

    def shutdown(self):
        self.stop()
        self.command_queue.put(Command(Actions.SHUTDOWN))

    def get_status(self) -> StatusAndError:
        if self.RE_running:
            return StatusAndError(Status.BUSY)
        last_result_success = (
            self.last_RE_result is None or self.last_RE_result.interrupted == False
        )
        if last_result_success:
            return StatusAndError(Status.IDLE)
        else:
            return StatusAndError(Status.FAILED, self.last_RE_result.reason)

    def wait_on_queue(self):
        while True:
            command = self.command_queue.get()
            if command.action == Actions.START:
                self.last_RE_result = self.RE(get_plan(command.parameters))
                self.RE_running = False
            elif command.action == Actions.SHUTDOWN:
                return


class FastGridScan(Resource):
    def __init__(self, runner: BlueskyRunner) -> None:
        super().__init__()
        self.runner = runner

    def put(self, action):
        status_and_message = StatusAndError(Status.FAILED, f"{action} not understood")
        if action == Actions.START.value:
            try:
                parameters = FullParameters.from_json(request.data)
                status_and_message = self.runner.start(parameters)
            except JSONDecodeError as e:
                status_and_message = StatusAndError(Status.FAILED, e.message)
        elif action == Actions.STOP.value:
            status_and_message = self.runner.stop()
        return status_and_message.to_dict()

    def get(self, action):
        if action == Actions.SHUTDOWN.value:
            self.runner.shutdown()
            shutdown_func = request.environ.get("werkzeug.server.shutdown")
            if globals.current_app.testing:
                return
            if shutdown_func is None:
                raise RuntimeError("Not running with the Werkzeug Server")
            shutdown_func()
        return self.runner.get_status().to_dict()


def create_app(test_config=None) -> Tuple[Flask, BlueskyRunner]:
    runner = BlueskyRunner()
    app = Flask(__name__)
    if test_config:
        app.config.update(test_config)
    api = Api(app)
    api.add_resource(
        FastGridScan, "/fast_grid_scan/<string:action>", resource_class_args=[runner]
    )
    return app, runner


if __name__ == "__main__":
    app, runner = create_app()
    flask_thread = threading.Thread(
        target=lambda: app.run(debug=True, use_reloader=False)
    )
    flask_thread.start()
    runner.wait_on_queue()
    flask_thread.join()
