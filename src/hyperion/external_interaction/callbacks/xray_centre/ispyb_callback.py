from __future__ import annotations

from time import time
from typing import TYPE_CHECKING, Any, Callable

import numpy as np
from dodal.devices.zocalo.zocalo_results import ZOCALO_READING_PLAN_NAME

from hyperion.external_interaction.callbacks.ispyb_callback_base import (
    BaseISPyBCallback,
)
from hyperion.external_interaction.exceptions import ISPyBDepositionNotMade
from hyperion.external_interaction.ispyb.gridscan_ispyb_store import (
    StoreGridscanInIspyb,
)
from hyperion.external_interaction.ispyb.gridscan_ispyb_store_2d import (
    Store2DGridscanInIspyb,
)
from hyperion.external_interaction.ispyb.gridscan_ispyb_store_3d import (
    Store3DGridscanInIspyb,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
)
from hyperion.log import ISPYB_LOGGER, set_dcgid_tag
from hyperion.parameters.constants import DO_FGS, GRIDSCAN_OUTER_PLAN
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)

if TYPE_CHECKING:
    from event_model import Event, RunStart, RunStop


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

    def __init__(
        self,
        *,
        emit: Callable[..., Any] | None = None,
    ) -> None:
        super().__init__()
        self.params: GridscanInternalParameters
        self.ispyb: StoreGridscanInIspyb
        self.ispyb_ids: IspybIds = IspybIds()
        self._start_of_fgs_uid: str | None = None
        self._processing_start_time: float | None = None

    def activity_gated_start(self, doc: RunStart):
        if doc.get("subplan_name") == DO_FGS:
            self._start_of_fgs_uid = doc.get("uid")
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
                # XXX Does this parameter even exist any more?
                if self.params.experiment_params.is_3d_grid_scan
                else Store2DGridscanInIspyb(self.ispyb_config, self.params)
            )
            self.ispyb_ids = self.ispyb.begin_deposition()

    def activity_gated_event(self, doc: Event):
        doc = super().activity_gated_event(doc)

        event_descriptor = self.descriptors[doc["descriptor"]]
        if event_descriptor.get("name") == ZOCALO_READING_PLAN_NAME:
            crystal_summary = ""
            if self._processing_start_time is not None:
                proc_time = time() - self._processing_start_time
                crystal_summary = f"Zocalo processing took {proc_time:.2f} s. "

            bboxes = []
            ISPYB_LOGGER.info(f"Amending comment based on Zocalo reading doc: {doc}")
            raw_results = doc["data"]["zocalo-results"]
            if len(raw_results) > 0:
                for n, res in enumerate(raw_results):
                    bboxes.append(
                        np.array(res["bounding_box"][1])
                        - np.array(res["bounding_box"][0])
                    )

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
            assert (
                self.ispyb_ids.data_collection_ids
            ), "No data collection to add results to"
            self.ispyb.append_to_comment(
                self.ispyb_ids.data_collection_ids[0], crystal_summary
            )

        set_dcgid_tag(self.ispyb_ids.data_collection_group_id)
        return doc

    def activity_gated_stop(self, doc: RunStop):
        if doc.get("run_start") == self._start_of_fgs_uid:
            self._processing_start_time = time()
        if doc.get("run_start") == self.uid_to_finalize_on:
            ISPYB_LOGGER.info(
                "ISPyB callback received stop document corresponding to start document "
                f"with uid: {self.uid_to_finalize_on}."
            )
            if self.ispyb_ids == IspybIds():
                raise ISPyBDepositionNotMade("ispyb was not initialised at run start")
            super().activity_gated_stop(doc)
