import argparse
import atexit
import json
import threading
import uuid
from dataclasses import dataclass
from json import JSONDecodeError
from queue import Queue
from traceback import format_exception
from typing import Callable, Optional, Tuple

from blueapi.core import BlueskyContext
from blueapi.worker import RunEngineWorker, RunPlan, Worker, run_worker_in_own_thread
from bluesky import RunEngine
from dataclasses_json import dataclass_json
from flask import Flask, request
from flask_restful import Api, Resource
from jsonschema.exceptions import ValidationError

import artemis.log
from artemis.exceptions import WarningException
from artemis.experiment_plans.experiment_registry import PLAN_REGISTRY, PlanNotFound
from artemis.experiment_plans.fast_grid_scan_plan import create_devices, fast_grid_scan
from artemis.external_interaction.callbacks.abstract_plan_callback_collection import (
    AbstractPlanCallbackCollection,
)
from artemis.external_interaction.callbacks.aperture_change_callback import (
    ApertureChangeCallback,
)
from artemis.external_interaction.callbacks.logging_callback import (
    VerbosePlanExecutionLoggingCallback,
)
from artemis.parameters.constants import Actions, Status
from artemis.parameters.internal_parameters import InternalParameters
from artemis.tracing import TRACER

VERBOSE_EVENT_LOGGING: Optional[bool] = None


@dataclass
class Command:
    action: Actions
    experiment: Optional[Callable] = None
    parameters: Optional[InternalParameters] = None


@dataclass_json
@dataclass
class StatusAndMessage:
    status: str
    message: str = ""

    def __init__(self, status: Status, message: str = "") -> None:
        self.status = status.value
        self.message = message


def setup_context(fake: bool, skip_startup_connection: bool) -> BlueskyContext:
    context = BlueskyContext()

    composite_device = create_devices(fake)
    context.device(composite_device)
    context.plan(fast_grid_scan)

    if not skip_startup_connection:
        for device in context.devices.values():
            if hasattr(device, "wait_for_connection"):
                device.wait_for_connection()

    return context


class RunExperiment(Resource):
    context: BlueskyContext
    worker: Worker

    def __init__(self, context: BlueskyContext, worker: Worker) -> None:
        super().__init__()
        self.context = context
        self.worker = worker

    def put(self, plan_name: str, action: Actions):
        status_and_message = StatusAndMessage(Status.FAILED, f"{action} not understood")
        if action == Actions.START.value:
            try:
                if plan_name not in self.context.plans:
                    raise PlanNotFound(
                        f"Experiment plan '{plan_name}' not found in registry."
                    )
                api_params = json.loads(request.data)
                params = {"apiParameters": api_params, "composite": "fast_grid_scan"}
                task = RunPlan(name=plan_name, params=params)
                task_id = str(uuid.uuid1())
                self.worker.submit_task(task_id, task)
                status_and_message = StatusAndMessage(Status.SUCCESS)
            except JSONDecodeError as e:
                status_and_message = StatusAndMessage(Status.FAILED, repr(e))
            except PlanNotFound as e:
                status_and_message = StatusAndMessage(Status.FAILED, repr(e))
            except ValidationError as e:
                status_and_message = StatusAndMessage(Status.FAILED, repr(e))
                artemis.log.LOGGER.error(
                    f" {format_exception(e)}: Invalid json parameters"
                )
            except Exception as e:
                status_and_message = StatusAndMessage(Status.FAILED, repr(e))
                artemis.log.LOGGER.error(format_exception(e))

        elif action == Actions.STOP.value:
            status_and_message = self.runner.stop()
        # no idea why mypy gives an attribute error here but nowhere else for this
        # exact same situation...
        return status_and_message.to_dict()  # type: ignore


class StopOrStatus(Resource):
    context: BlueskyContext
    worker: Worker

    def __init__(self, worker: Worker) -> None:
        super().__init__()
        self.worker = worker

    def put(self, action):
        return NotImplemented
        status_and_message = StatusAndMessage(Status.FAILED, f"{action} not understood")
        if action == Actions.STOP.value:
            status_and_message = self.worke
        return status_and_message.to_dict()

    def get(self, **kwargs):
        return NotImplemented
        action = kwargs.get("action")
        status_and_message = StatusAndMessage(Status.FAILED, f"{action} not understood")
        if action == Actions.STATUS.value:
            status_and_message = self.worker
        return status_and_message.to_dict()


def create_app(
    test_config=None, RE: RunEngine = RunEngine({}), skip_startup_connection=False
) -> Tuple[Flask, Worker, BlueskyContext]:
    context = setup_context(
        fake=False,
        skip_startup_connection=skip_startup_connection,
    )
    worker = RunEngineWorker(context)
    app = Flask(__name__)
    if test_config:
        app.config.update(test_config)
    api = Api(app)
    api.add_resource(
        RunExperiment,
        "/<string:plan_name>/<string:action>",
        resource_class_args=[context, worker],
    )
    api.add_resource(
        StopOrStatus,
        "/<string:action>",
        resource_class_args=[worker],
    )
    return app, worker, context


def cli_arg_parse() -> (
    Tuple[Optional[str], Optional[bool], Optional[bool], Optional[bool]]
):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Use dev options, such as local graylog instances and S03",
    )
    parser.add_argument(
        "--verbose-event-logging",
        action="store_true",
        help="Log all bluesky event documents to graylog",
    )
    parser.add_argument(
        "--logging-level",
        type=str,
        choices=["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"],
        help="Choose overall logging level, defaults to INFO",
    )
    parser.add_argument(
        "--skip-startup-connection",
        action="store_true",
        help="Skip connecting to EPICS PVs on startup",
    )
    args = parser.parse_args()
    return (
        args.logging_level,
        args.verbose_event_logging,
        args.dev,
        args.skip_startup_connection,
    )


if __name__ == "__main__":
    artemis_port = 5005
    (
        logging_level,
        VERBOSE_EVENT_LOGGING,
        dev_mode,
        skip_startup_connection,
    ) = cli_arg_parse()

    artemis.log.set_up_logging_handlers(logging_level, dev_mode)
    app, worker, context = create_app(skip_startup_connection=skip_startup_connection)
    # atexit.register(runner.shutdown)
    flask_thread = threading.Thread(
        target=lambda: app.run(
            host="0.0.0.0", port=artemis_port, debug=True, use_reloader=False
        ),
        daemon=True,
    )
    flask_thread.start()
    artemis.log.LOGGER.info(
        f"Artemis now listening on {artemis_port} ({'IN DEV' if dev_mode else ''})"
    )
    # runner.wait_on_queue()
    worker.start()
    flask_thread.join()
