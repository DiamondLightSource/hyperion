import atexit
import threading
from dataclasses import asdict
from queue import Queue
from traceback import format_exception
from typing import Any, Callable, Optional, Tuple

from blueapi.core import BlueskyContext, MsgGenerator
from bluesky.callbacks.zmq import Publisher
from bluesky.run_engine import RunEngine
from flask import Flask, request
from flask_restful import Api, Resource
from pydantic.dataclasses import dataclass

from hyperion.exceptions import WarningException
from hyperion.experiment_plans.experiment_registry import (
    PLAN_REGISTRY,
    CallbackFactories,
    PlanNotFound,
)
from hyperion.external_interaction.callbacks.__main__ import (
    setup_logging as setup_callback_logging,
)
from hyperion.external_interaction.callbacks.aperture_change_callback import (
    ApertureChangeCallback,
)
from hyperion.external_interaction.callbacks.log_uid_tag_callback import (
    LogUidTaggingCallback,
)
from hyperion.external_interaction.callbacks.logging_callback import (
    VerbosePlanExecutionLoggingCallback,
)
from hyperion.log import LOGGER, do_default_logging_setup
from hyperion.parameters.cli import parse_cli_args
from hyperion.parameters.constants import CONST, Actions, Status
from hyperion.parameters.internal_parameters import InternalParameters
from hyperion.tracing import TRACER
from hyperion.utils.context import setup_context

VERBOSE_EVENT_LOGGING: Optional[bool] = None


@dataclass
class Command:
    action: Actions
    devices: Optional[Any] = None
    experiment: Optional[Callable[[Any, Any], MsgGenerator]] = None
    parameters: Optional[InternalParameters] = None
    callbacks: Optional[CallbackFactories] = None


@dataclass
class StatusAndMessage:
    status: str
    message: str = ""

    def __init__(self, status: Status, message: str = "") -> None:
        self.status = status.value
        self.message = message


@dataclass
class ErrorStatusAndMessage(StatusAndMessage):
    exception_type: str = ""

    def __init__(self, exception: Exception) -> None:
        super().__init__(Status.FAILED, repr(exception))
        self.exception_type = type(exception).__name__


class BlueskyRunner:
    def __init__(
        self,
        RE: RunEngine,
        context: BlueskyContext,
        skip_startup_connection=False,
        use_external_callbacks: bool = False,
    ) -> None:
        self.command_queue: Queue[Command] = Queue()
        self.current_status: StatusAndMessage = StatusAndMessage(Status.IDLE)
        self.last_run_aborted: bool = False
        self.aperture_change_callback = ApertureChangeCallback()
        self.logging_uid_tag_callback = LogUidTaggingCallback()
        self.context: BlueskyContext

        self.RE = RE
        self.context = context
        self.subscribed_per_plan_callbacks: list[int] = []
        RE.subscribe(self.aperture_change_callback)
        RE.subscribe(self.logging_uid_tag_callback)

        self.use_external_callbacks = use_external_callbacks
        if self.use_external_callbacks:
            LOGGER.info("Connecting to external callback ZMQ proxy...")
            self.publisher = Publisher(f"localhost:{CONST.CALLBACK_0MQ_PROXY_PORTS[0]}")
            RE.subscribe(self.publisher)

        if VERBOSE_EVENT_LOGGING:
            RE.subscribe(VerbosePlanExecutionLoggingCallback())

        self.skip_startup_connection = skip_startup_connection
        if not self.skip_startup_connection:
            LOGGER.info("Initialising dodal devices...")
            for plan_name in PLAN_REGISTRY:
                PLAN_REGISTRY[plan_name]["setup"](context)

    def start(
        self,
        experiment: Callable,
        parameters: InternalParameters,
        plan_name: str,
        callbacks: Optional[CallbackFactories],
    ) -> StatusAndMessage:
        LOGGER.info(f"Started with parameters: {parameters}")

        devices: Any = PLAN_REGISTRY[plan_name]["setup"](self.context)

        if (
            self.current_status.status == Status.BUSY.value
            or self.current_status.status == Status.ABORTING.value
        ):
            return StatusAndMessage(Status.FAILED, "Bluesky already running")
        else:
            self.current_status = StatusAndMessage(Status.BUSY)
            self.command_queue.put(
                Command(
                    action=Actions.START,
                    devices=devices,
                    experiment=experiment,
                    parameters=parameters,
                    callbacks=callbacks,
                )
            )
            return StatusAndMessage(Status.SUCCESS)

    def stopping_thread(self):
        try:
            self.RE.abort()
            self.current_status = StatusAndMessage(Status.IDLE)
        except Exception as e:
            self.current_status = ErrorStatusAndMessage(e)

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
        self.command_queue.put(Command(action=Actions.SHUTDOWN))

    def wait_on_queue(self):
        while True:
            command = self.command_queue.get()
            if command.action == Actions.SHUTDOWN:
                return
            elif command.action == Actions.START:
                if command.experiment is None:
                    raise ValueError("No experiment provided for START")
                try:
                    if (
                        not self.use_external_callbacks
                        and command.callbacks
                        and (cbs := command.callbacks())
                    ):
                        LOGGER.info(
                            f"Using callbacks for this plan: {not self.use_external_callbacks} - {cbs}"
                        )
                        self.subscribed_per_plan_callbacks += [
                            self.RE.subscribe(cb) for cb in cbs
                        ]
                    with TRACER.start_span("do_run"):
                        self.RE(command.experiment(command.devices, command.parameters))

                    self.current_status = StatusAndMessage(
                        Status.IDLE,
                        self.aperture_change_callback.last_selected_aperture,
                    )

                    self.last_run_aborted = False
                except WarningException as exception:
                    LOGGER.warning("Warning Exception", exc_info=True)
                    self.current_status = ErrorStatusAndMessage(exception)
                except Exception as exception:
                    LOGGER.error("Exception on running plan", exc_info=True)

                    if self.last_run_aborted:
                        # Aborting will cause an exception here that we want to swallow
                        self.last_run_aborted = False
                    else:
                        self.current_status = ErrorStatusAndMessage(exception)
                finally:
                    [
                        self.RE.unsubscribe(cb)
                        for cb in self.subscribed_per_plan_callbacks
                    ]


def compose_start_args(context: BlueskyContext, plan_name: str, action: Actions):
    experiment_registry_entry = PLAN_REGISTRY.get(plan_name)
    if experiment_registry_entry is None:
        raise PlanNotFound(f"Experiment plan '{plan_name}' not found in registry.")

    experiment_internal_param_type = experiment_registry_entry.get(
        "internal_param_type"
    )
    callback_type = experiment_registry_entry.get("callback_collection_type")
    plan = context.plan_functions.get(plan_name)
    if experiment_internal_param_type is None:
        raise PlanNotFound(
            f"Corresponding internal param type for '{plan_name}' not found in registry."
        )
    if plan is None:
        raise PlanNotFound(
            f"Experiment plan '{plan_name}' not found in context. Context has {context.plan_functions.keys()}"
        )

    parameters = experiment_internal_param_type.from_json(request.data)
    if plan_name != parameters.hyperion_params.experiment_type:
        raise PlanNotFound(
            f"Wrong experiment parameters ({parameters.hyperion_params.experiment_type}) "
            f"for plan endpoint {plan_name}."
        )
    return plan, parameters, plan_name, callback_type


class RunExperiment(Resource):
    def __init__(self, runner: BlueskyRunner, context: BlueskyContext) -> None:
        super().__init__()
        self.runner = runner
        self.context = context

    def put(self, plan_name: str, action: Actions):
        status_and_message = StatusAndMessage(Status.FAILED, f"{action} not understood")
        if action == Actions.START.value:
            try:
                plan, params, plan_name, callback_type = compose_start_args(
                    self.context, plan_name, action
                )
                status_and_message = self.runner.start(
                    plan, params, plan_name, callback_type
                )
            except Exception as e:
                status_and_message = ErrorStatusAndMessage(e)
                LOGGER.error(format_exception(e))

        elif action == Actions.STOP.value:
            status_and_message = self.runner.stop()
        # no idea why mypy gives an attribute error here but nowhere else for this
        # exact same situation...
        return asdict(status_and_message)  # type: ignore


class StopOrStatus(Resource):
    def __init__(self, runner: BlueskyRunner) -> None:
        super().__init__()
        self.runner: BlueskyRunner = runner

    def put(self, action):
        status_and_message = StatusAndMessage(Status.FAILED, f"{action} not understood")
        if action == Actions.STOP.value:
            status_and_message = self.runner.stop()
        return asdict(status_and_message)

    def get(self, **kwargs):
        action = kwargs.get("action")
        status_and_message = StatusAndMessage(Status.FAILED, f"{action} not understood")
        if action == Actions.STATUS.value:
            LOGGER.debug(
                f"Runner recieved status request - state of the runner object is: {self.runner.__dict__} - state of the RE is: {self.runner.RE.__dict__}"
            )
            status_and_message = self.runner.current_status
        return asdict(status_and_message)


def create_app(
    test_config=None,
    RE: RunEngine = RunEngine({}),
    skip_startup_connection: bool = False,
    use_external_callbacks: bool = False,
) -> Tuple[Flask, BlueskyRunner]:
    context = setup_context(
        wait_for_connection=not skip_startup_connection,
    )
    runner = BlueskyRunner(
        RE,
        context=context,
        use_external_callbacks=use_external_callbacks,
        skip_startup_connection=skip_startup_connection,
    )
    app = Flask(__name__)
    if test_config:
        app.config.update(test_config)
    api = Api(app)
    api.add_resource(
        RunExperiment,
        "/<string:plan_name>/<string:action>",
        resource_class_args=[runner, context],
    )
    api.add_resource(
        StopOrStatus,
        "/<string:action>",
        resource_class_args=[runner],
    )
    return app, runner


def create_targets():
    hyperion_port = 5005
    args = parse_cli_args()
    do_default_logging_setup(dev_mode=args.dev_mode)
    if not args.use_external_callbacks:
        setup_callback_logging(args.dev_mode)
    app, runner = create_app(
        skip_startup_connection=args.skip_startup_connection,
        use_external_callbacks=args.use_external_callbacks,
    )
    return app, runner, hyperion_port, args.dev_mode


def main():
    app, runner, port, dev_mode = create_targets()
    atexit.register(runner.shutdown)
    flask_thread = threading.Thread(
        target=lambda: app.run(
            host="0.0.0.0", port=port, debug=True, use_reloader=False
        ),
        daemon=True,
    )
    flask_thread.start()
    LOGGER.info(f"Hyperion now listening on {port} ({'IN DEV' if dev_mode else ''})")
    runner.wait_on_queue()
    flask_thread.join()


if __name__ == "__main__":
    main()
