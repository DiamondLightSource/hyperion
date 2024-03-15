from __future__ import annotations

from typing import TYPE_CHECKING, Dict

from hyperion.external_interaction.callbacks.plan_reactive_callback import (
    PlanReactiveCallback,
)
from hyperion.external_interaction.nexus.nexus_utils import (
    create_beam_and_attenuator_parameters,
)
from hyperion.external_interaction.nexus.write_nexus import NexusWriter
from hyperion.log import NEXUS_LOGGER
from hyperion.parameters.constants import CONST
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)

if TYPE_CHECKING:
    from event_model.documents import Event, EventDescriptor, RunStart


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
        self.run_start_uid: str | None = None
        self.nexus_writer_1: NexusWriter | None = None
        self.nexus_writer_2: NexusWriter | None = None
        self.descriptors: Dict[str, EventDescriptor] = {}
        self.log = NEXUS_LOGGER

    def activity_gated_start(self, doc: RunStart):
        if doc.get("subplan_name") == CONST.PLAN.GRIDSCAN_OUTER:
            json_params = doc.get("hyperion_internal_parameters")
            NEXUS_LOGGER.info(
                f"Nexus writer received start document with experiment parameters {json_params}"
            )
            parameters = GridscanInternalParameters.from_json(json_params)
            nexus_data_1 = parameters.get_nexus_info(1)
            nexus_data_2 = parameters.get_nexus_info(2)
            self.nexus_writer_1 = NexusWriter(parameters, **nexus_data_1)
            self.nexus_writer_2 = NexusWriter(
                parameters,
                **nexus_data_2,
                vds_start_index=nexus_data_1["data_shape"][0],
            )
            self.run_start_uid = doc.get("uid")

    def activity_gated_descriptor(self, doc: EventDescriptor):
        self.descriptors[doc["uid"]] = doc

    def activity_gated_event(self, doc: Event) -> Event | None:
        event_descriptor = self.descriptors.get(doc["descriptor"])
        if (
            event_descriptor
            and event_descriptor.get("name") == CONST.PLAN.ISPYB_TRANSMISSION_FLUX_READ
        ):
            data = doc["data"]
            for nexus_writer in [self.nexus_writer_1, self.nexus_writer_2]:
                assert nexus_writer, "Nexus callback did not receive start doc"
                nexus_writer.beam, nexus_writer.attenuator = (
                    create_beam_and_attenuator_parameters(
                        data["dcm_energy_in_kev"],
                        data["flux_flux_reading"],
                        data["attenuator_actual_transmission"],
                    )
                )
                nexus_writer.create_nexus_file()
                NEXUS_LOGGER.info(f"Nexus file created at {nexus_writer.full_filename}")

        return super().activity_gated_event(doc)
