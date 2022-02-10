from dataclasses import dataclass
import json
import bluesky
from click import Parameter
from flask import Flask, jsonify, request
from flask_restful import Resource, Api
import logging
from threading import Thread
from time import sleep
from typing import Tuple
from enum import Enum


logger = logging.getLogger(__name__)


class Actions(Enum):
    START = "start"
    STOP = "stop"


class Status(Enum):
    FAILED = "Failed"
    SUCCESS = "Success"
    BUSY = "Busy"
    IDLE = "Idle"


@dataclass
class StatusAndError:
    status: Status
    error: str = ""


class BlueskyRunner(object):
    def __init__(self) -> None:
        self.bluesky_running = False
        self.error = None

    def start(self, parameters) -> StatusAndError:
        print(f"Params are: {parameters}")
        if self.bluesky_running:
            return StatusAndError(Status.FAILED, "Bluesky already running")
        self.bluesky_running = True
        self.error = None
        self.bluesky_thread = Thread(target=self.do_plan, daemon=True)
        self.bluesky_thread.start()
        return StatusAndError(Status.SUCCESS)

    def do_plan(self):
        while self.bluesky_running:
            sleep(0.01)

    def stop(self) -> StatusAndError:
        if not self.bluesky_running:
            return StatusAndError(Status.FAILED, "Bluesky not running")
        self.bluesky_running = False
        self.bluesky_thread.join()
        return StatusAndError(Status.SUCCESS)

    def set_error(self, error_message):
        self.error = error_message
        self.bluesky_running = False

    def get_status(self) -> StatusAndError:
        if self.bluesky_running:
            return StatusAndError(Status.BUSY)
        elif self.error is not None:
            return StatusAndError(Status.FAILED, self.error)
        else:
            return StatusAndError(Status.IDLE)


class FastGridScan(Resource):
    def __init__(self, runner: BlueskyRunner) -> None:
        super().__init__()
        self.runner = runner

    def _craft_return_message(self, status_and_message: StatusAndError):
        return jsonify(
            {
                "status": status_and_message.status.value,
                "message": status_and_message.error,
            }
        )

    def put(self, action):
        status_and_message = StatusAndError(Status.FAILED, f"{action} not understood")
        if action == Actions.START.value:
            parameters = json.loads(request.data)
            status_and_message = self.runner.start(parameters)
        elif action == Actions.STOP.value:
            status_and_message = self.runner.stop()
        return self._craft_return_message(status_and_message)

    def get(self, action):
        return self._craft_return_message(self.runner.get_status())


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
    app.run(debug=True)
