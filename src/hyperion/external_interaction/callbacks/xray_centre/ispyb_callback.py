from __future__ import annotations

from time import time
from typing import List

import numpy as np
from dodal.devices.zocalo.zocalo_results import ZOCALO_READING_PLAN_NAME
from event_model.documents.event import Event

from hyperion.external_interaction.callbacks.ispyb_callback_base import (
    BaseISPyBCallback,
)
from hyperion.external_interaction.exceptions import ISPyBDepositionNotMade
from hyperion.external_interaction.ispyb.store_datacollection_in_ispyb import (
    IspybIds,
    Store2DGridscanInIspyb,
    Store3DGridscanInIspyb,
    StoreGridscanInIspyb,
)
from hyperion.log import ISPYB_LOGGER, set_dcgid_tag
from hyperion.parameters.constants import GRIDSCAN_OUTER_PLAN
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)


class GridscanISPyBCallback(BaseISPyBCallback):
    """Callback class to handle the deposition of experiment parameters into the ISPyB
    database. Listens for 'event' and 'descriptor' documents. Creates the ISpyB entry on
    recieving an 'event' document for the 'ispyb_reading_hardware' event, and updates the
    deposition on recieving its final 'stop' document.

    To use, subscribe the Bluesky RunEngine to an instance of this class.
    E.g.:
        ispyb_handler_callback = FGSISPyBCallback(parameters)
        RE.subscribe(ispyb_handler_callback)
    Or decorate a plan using bluesky.preprocessors.subs_decorator.

    See: https://blueskyproject.io/bluesky/callbacks.html#ways-to-invoke-callbacks

    Usually used as part of an FGSCallbackCollection.
    """

    def __init__(self) -> None:
        super().__init__()
        self.params: GridscanInternalParameters
        self.ispyb: StoreGridscanInIspyb
        self.ispyb_ids: IspybIds = IspybIds()
        self.processing_start_time: float | None = None

    def activity_gated_start(self, doc: dict):
        if doc.get("subplan_name") == GRIDSCAN_OUTER_PLAN:
            self.uid_to_finalize_on = doc.get("uid")
            ISPYB_LOGGER.info(
                "ISPyB callback recieved start document with experiment parameters and "
                f"uid: {self.uid_to_finalize_on}"
            )
            json_params = doc.get("hyperion_internal_parameters")
            self.params = GridscanInternalParameters.from_json(json_params)
            self.ispyb = (
                Store3DGridscanInIspyb(self.ispyb_config, self.params)
                if self.params.experiment_params.is_3d_grid_scan
                else Store2DGridscanInIspyb(self.ispyb_config, self.params)
            )

    def activity_gated_event(self, doc: Event):
        super().activity_gated_event(doc)

        event_descriptor = self.descriptors[doc["descriptor"]]
        if event_descriptor.get("name") == ZOCALO_READING_PLAN_NAME:
            crystal_summary = ""
            if self.processing_start_time is not None:
                proc_time = time() - self.processing_start_time
                crystal_summary = f"Zocalo processing took {proc_time:.2f} s. "

            bboxes: List[np.ndarray] = []
            ISPYB_LOGGER.info(f"Amending comment based on Zocalo reading doc: {doc}")
            raw_results = doc["data"]["zocalo-results"]
            if len(raw_results) > 0:
                for n, res in enumerate(raw_results):
                    bb = res["bounding_box"]
                    diff = np.array(bb[1]) - np.array(bb[0])
                    bboxes.append(diff)

                    nicely_formatted_com = [
                        f"{np.round(com, 2)}" for com in res["centre_of_mass"]
                    ]
                    crystal_summary += (
                        f"Crystal {n + 1}: "
                        f"Strength {res['total_count']}; "
                        f"Position (grid boxes) {nicely_formatted_com}; "
                        f"Size (grid boxes) {bboxes[n]}; "
                    )
            else:
                crystal_summary += "Zocalo found no crystals in this gridscan."
            assert isinstance(self.ispyb_ids.data_collection_ids, tuple)
            self.ispyb.append_to_comment(
                self.ispyb_ids.data_collection_ids[0], crystal_summary
            )

        set_dcgid_tag(self.ispyb_ids.data_collection_group_id)

    def activity_gated_stop(self, doc: dict):
        if doc.get("run_start") == self.uid_to_finalize_on:
            ISPYB_LOGGER.info(
                "ISPyB callback received stop document corresponding to start document "
                f"with uid: {self.uid_to_finalize_on}."
            )
            if self.ispyb_ids == IspybIds():
                raise ISPyBDepositionNotMade("ispyb was not initialised at run start")
            super().activity_gated_stop(doc)

    def append_to_comment(self, comment: str):
        assert isinstance(self.ispyb_ids.data_collection_ids, tuple)
        for id in self.ispyb_ids.data_collection_ids:
            self._append_to_comment(id, comment)
