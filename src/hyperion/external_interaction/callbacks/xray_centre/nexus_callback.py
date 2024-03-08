from __future__ import annotations

from typing import TYPE_CHECKING

from hyperion.external_interaction.callbacks.plan_reactive_callback import (
    PlanReactiveCallback,
)
from hyperion.external_interaction.nexus.write_nexus import NexusWriter
from hyperion.log import NEXUS_LOGGER
from hyperion.parameters.constants import CONST
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)

if TYPE_CHECKING:
    from event_model.documents import EventDescriptor, RunStart


class GridscanNexusFileCallback(PlanReactiveCallback):
    """Callback class to handle the creation of Nexus files based on experiment \
    parameters. Initialises on recieving a 'start' document for the \
    'run_gridscan_move_and_tidy' sub plan, which must also contain the run parameters, \
    as metadata under the 'hyperion_internal_parameters' key. Actually writes the \
    nexus files on updates the timestamps on recieving the 'ispyb_reading_hardware' event \
    document, and finalises the files on getting a 'stop' document for the whole run.

    To use, subscribe the Bluesky RunEngine to an instance of this class.
    E.g.:
        nexus_file_handler_callback = NexusFileCallback(parameters)
        RE.subscribe(nexus_file_handler_callback)
    Or decorate a plan using bluesky.preprocessors.subs_decorator.

    See: https://blueskyproject.io/bluesky/callbacks.html#ways-to-invoke-callbacks

    Usually used as part of an FGSCallbackCollection.
    """

    def __init__(self) -> None:
        super().__init__(NEXUS_LOGGER)
        self.parameters: GridscanInternalParameters | None = None
        self.run_start_uid: str | None = None
        self.nexus_writer_1: NexusWriter | None = None
        self.nexus_writer_2: NexusWriter | None = None
        self.log = NEXUS_LOGGER

    def activity_gated_start(self, doc: RunStart):
        if doc.get("subplan_name") == CONST.PLAN.GRIDSCAN_OUTER:
            json_params = doc.get("hyperion_internal_parameters")
            NEXUS_LOGGER.info(
                f"Nexus writer recieved start document with experiment parameters {json_params}"
            )
            self.parameters = GridscanInternalParameters.from_json(json_params)
            self.run_start_uid = doc.get("uid")

    def activity_gated_descriptor(self, doc: EventDescriptor):
        if doc.get("name") == CONST.PLAN.ISPYB_HARDWARE_READ:
            assert (
                self.parameters is not None
            ), "Nexus callback did not receive parameters before being asked to write!"
            # TODO instead of ispyb wait for detector parameter reading in plan
            # https://github.com/DiamondLightSource/python-hyperion/issues/629
            # and update parameters before creating writers

            NEXUS_LOGGER.info("Initialising nexus writers...")
            nexus_data_1 = self.parameters.get_nexus_info(1)
            nexus_data_2 = self.parameters.get_nexus_info(2)
            self.nexus_writer_1 = NexusWriter(self.parameters, **nexus_data_1)
            self.nexus_writer_2 = NexusWriter(
                self.parameters,
                **nexus_data_2,
                vds_start_index=nexus_data_1["data_shape"][0],
            )
            self.nexus_writer_1.create_nexus_file()
            self.nexus_writer_2.create_nexus_file()
            NEXUS_LOGGER.info(
                f"Nexus files created at {self.nexus_writer_1.full_filename} and {self.nexus_writer_1.full_filename}"
            )
