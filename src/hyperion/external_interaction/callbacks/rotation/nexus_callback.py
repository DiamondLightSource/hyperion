from __future__ import annotations

from typing import TYPE_CHECKING, Dict

import numpy as np
from numpy.typing import DTypeLike

from hyperion.external_interaction.callbacks.plan_reactive_callback import (
    PlanReactiveCallback,
)
from hyperion.external_interaction.nexus.nexus_utils import vds_type_based_on_bit_depth
from hyperion.external_interaction.nexus.write_nexus import NexusWriter
from hyperion.log import NEXUS_LOGGER
from hyperion.parameters.constants import NEXUS_READ_PLAN, ROTATION_OUTER_PLAN
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)

if TYPE_CHECKING:
    from event_model.documents import Event, EventDescriptor, RunStart


class RotationNexusFileCallback(PlanReactiveCallback):
    """Callback class to handle the creation of Nexus files based on experiment
    parameters for rotation scans

    To use, subscribe the Bluesky RunEngine to an instance of this class.
    E.g.:
        nexus_file_handler_callback = NexusFileCallback(parameters)
        RE.subscribe(nexus_file_handler_callback)
    Or decorate a plan using bluesky.preprocessors.subs_decorator.

    See: https://blueskyproject.io/bluesky/callbacks.html#ways-to-invoke-callbacks

    Usually used as part of a RotationCallbackCollection.
    """

    def __init__(self) -> None:
        super().__init__(NEXUS_LOGGER)
        self.run_uid: str | None = None
        self.parameters: RotationInternalParameters | None = None
        self.writer: NexusWriter | None = None
        self.descriptors: Dict[str, EventDescriptor] = {}
        self.data_bit_depth: DTypeLike = np.uint16

    def activity_gated_descriptor(self, doc: EventDescriptor):
        self.descriptors[doc["uid"]] = doc

    def activity_gated_event(self, doc: Event):
        event_descriptor = self.descriptors.get(doc["descriptor"])
        if event_descriptor is None:
            NEXUS_LOGGER.warning(
                f"Rotation Nexus handler {self} received event doc {doc} and "
                "has no corresponding descriptor record"
            )
            return doc
        if event_descriptor.get("name") == NEXUS_READ_PLAN:
            NEXUS_LOGGER.info(f"Nexus handler received event from read hardware {doc}")
            vds_data_type = vds_type_based_on_bit_depth(doc["data"]["eiger_bit_depth"])
            assert self.writer is not None
            self.writer.create_nexus_file(vds_data_type)
            NEXUS_LOGGER.info(f"Nexus file created at {self.writer.full_filename}")
        return doc

    def activity_gated_start(self, doc: RunStart):
        if doc.get("subplan_name") == ROTATION_OUTER_PLAN:
            self.run_uid = doc.get("uid")
            json_params = doc.get("hyperion_internal_parameters")
            NEXUS_LOGGER.info(
                f"Nexus writer received start document with experiment parameters {json_params}"
            )
            self.parameters = RotationInternalParameters.from_json(json_params)
            NEXUS_LOGGER.info("Setting up nexus file...")
            self.writer = NexusWriter(
                self.parameters,
                self.parameters.get_scan_points(),
                self.parameters.get_data_shape(),
            )
