from __future__ import annotations

from bluesky.callbacks import CallbackBase

from artemis.external_interaction.nexus.write_nexus import (
    FGSNexusWriter,
    create_3d_gridscan_writers,
)
from artemis.log import LOGGER
from artemis.parameters.plan_specific.fgs_internal_params import FGSInternalParameters


class FGSNexusFileHandlerCallback(CallbackBase):
    """Callback class to handle the creation of Nexus files based on experiment
    parameters. Creates the Nexus files on recieving a 'start' document for the
    'run_gridscan' sub plan, and updates the timestamps on recieving a 'stop' document
    for the same.

    To use, subscribe the Bluesky RunEngine to an instance of this class.
    E.g.:
        nexus_file_handler_callback = NexusFileHandlerCallback(parameters)
        RE.subscribe(nexus_file_handler_callback)
    Or decorate a plan using bluesky.preprocessors.subs_decorator.

    See: https://blueskyproject.io/bluesky/callbacks.html#ways-to-invoke-callbacks

    Usually used as part of an FGSCallbackCollection.
    """

    def __init__(self) -> None:
        self.parameters: FGSInternalParameters | None = None
        self.run_gridscan_uid: str | None = None
        self.nexus_writer_1: FGSNexusWriter | None = None
        self.nexus_writer_2: FGSNexusWriter | None = None

    def start(self, doc: dict):
        if doc.get("subplan_name") == "run_gridscan_move_and_tidy":
            LOGGER.info(
                "Nexus writer recieved start document with experiment parameters."
            )
            json_params = doc.get("hyperion_internal_parameters")
            self.parameters = FGSInternalParameters.from_json(json_params)
        elif doc.get("subplan_name") == "run_gridscan":
            LOGGER.info("Initialising nexus writers")
            self.run_gridscan_uid = doc.get("uid")
            self.nexus_writer_1, self.nexus_writer_2 = create_3d_gridscan_writers(
                self.parameters
            )

    def event(self, doc: dict):
        # TODO get ispyb data into params
        ...

    def stop(self, doc: dict):
        if (
            self.run_gridscan_uid is not None
            and doc.get("run_start") == self.run_gridscan_uid
        ):
            LOGGER.info("Updating Nexus file timestamps.")
            assert (
                self.nexus_writer_1 is not None and self.nexus_writer_2 is not None
            ), "Failed to update Nexus file timestamps, writers were not initialised."
            self.nexus_writer_1.update_nexus_file_timestamp()
            self.nexus_writer_2.update_nexus_file_timestamp()
