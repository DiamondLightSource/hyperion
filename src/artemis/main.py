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


class BlueskyRunner(object):
    def __init__(self) -> None:
        self.bluesky_running = False
        self.bluesky_thread = Thread(target=self.do_plan, daemon=True)

    def start(self, parameters):
        print(f"Params are: {parameters}")
        if self.bluesky_running:
            return False
        self.bluesky_running = True
        self.bluesky_thread.start()
        return True

    def do_plan(self):
        while self.bluesky_running:
            sleep(0.01)

    def stop(self):
        if not self.bluesky_running:
            return False
        self.bluesky_running = False
        self.bluesky_thread.join()
        return True


class FastGridScan(Resource):
    def __init__(self, runner: BlueskyRunner) -> None:
        super().__init__()
        self.runner = runner

    def put(self, action):
        status = Status.FAILED
        if action == Actions.START.value:
            parameters = json.loads(request.data)
            status = Status.SUCCESS if self.runner.start(parameters) else Status.FAILED
        elif action == Actions.STOP.value:
            status = Status.SUCCESS if self.runner.stop() else Status.FAILED
        return jsonify({"status": status.value})

    def get(self, action):
        status = Status.BUSY if self.runner.bluesky_running else Status.IDLE
        return jsonify({"status": status.value})


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
