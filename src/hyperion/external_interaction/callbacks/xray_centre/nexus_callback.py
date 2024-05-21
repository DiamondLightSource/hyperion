from __future__ import annotations

from typing import TYPE_CHECKING, Dict

from hyperion.external_interaction.callbacks.plan_reactive_callback import (
    PlanReactiveCallback,
)
from hyperion.external_interaction.nexus.nexus_utils import (
    create_beam_and_attenuator_parameters,
    vds_type_based_on_bit_depth,
)
from hyperion.external_interaction.nexus.write_nexus import NexusWriter
from hyperion.log import NEXUS_LOGGER
from hyperion.parameters.constants import CONST
from hyperion.parameters.gridscan import ThreeDGridScan

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
            json_params = doc.get("hyperion_parameters")
            NEXUS_LOGGER.info(
                f"Nexus writer received start document with experiment parameters {json_params}"
            )
            parameters = ThreeDGridScan.from_json(json_params)
            d_size = parameters.detector_params.detector_size_constants.det_size_pixels
            grid_n_img_1 = parameters.scan_indices[1]
            grid_n_img_2 = parameters.num_images - grid_n_img_1
            data_shape_1 = (grid_n_img_1, d_size.width, d_size.height)
            data_shape_2 = (grid_n_img_2, d_size.width, d_size.height)
            run_number_2 = parameters.detector_params.run_number + 1
            self.nexus_writer_1 = NexusWriter(
                parameters, data_shape_1, parameters.scan_points_1
            )
            self.nexus_writer_2 = NexusWriter(
                parameters,
                data_shape_2,
                parameters.scan_points_2,
                run_number=run_number_2,
                vds_start_index=parameters.scan_indices[1],
                omega_start_deg=90,
            )
            self.run_start_uid = doc.get("uid")

    def activity_gated_descriptor(self, doc: EventDescriptor):
        self.descriptors[doc["uid"]] = doc

    def activity_gated_event(self, doc: Event) -> Event | None:
        assert (event_descriptor := self.descriptors.get(doc["descriptor"])) is not None
        if (
            event_descriptor.get("name")
            == CONST.DESCRIPTORS.ISPYB_TRANSMISSION_FLUX_READ
        ):
            data = doc["data"]
            for nexus_writer in [self.nexus_writer_1, self.nexus_writer_2]:
                assert nexus_writer, "Nexus callback did not receive start doc"
                (
                    nexus_writer.beam,
                    nexus_writer.attenuator,
                ) = create_beam_and_attenuator_parameters(
                    data["dcm-energy_in_kev"],
                    data["flux_flux_reading"],
                    data["attenuator_actual_transmission"],
                )
        if event_descriptor.get("name") == CONST.DESCRIPTORS.NEXUS_READ:
            NEXUS_LOGGER.info(f"Nexus handler received event from read hardware {doc}")
            for nexus_writer in [self.nexus_writer_1, self.nexus_writer_2]:
                vds_data_type = vds_type_based_on_bit_depth(
                    doc["data"]["eiger_bit_depth"]
                )
                assert nexus_writer, "Nexus callback did not receive start doc"
                nexus_writer.create_nexus_file(vds_data_type)
                NEXUS_LOGGER.info(f"Nexus file created at {nexus_writer.full_filename}")

        return super().activity_gated_event(doc)
