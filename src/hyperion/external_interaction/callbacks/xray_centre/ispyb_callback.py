from __future__ import annotations

from collections.abc import Sequence
from time import time
from typing import TYPE_CHECKING, Any, Callable, List, cast

import numpy as np
from bluesky import preprocessors as bpp
from dodal.devices.zocalo.zocalo_results import ZOCALO_READING_PLAN_NAME

from hyperion.external_interaction.callbacks.common.ispyb_mapping import (
    populate_data_collection_group,
    populate_data_collection_position_info,
    populate_remaining_data_collection_info,
)
from hyperion.external_interaction.callbacks.ispyb_callback_base import (
    BaseISPyBCallback,
)
from hyperion.external_interaction.callbacks.xray_centre.ispyb_mapping import (
    populate_xy_data_collection_info,
    populate_xz_data_collection_info,
)
from hyperion.external_interaction.exceptions import ISPyBDepositionNotMade
from hyperion.external_interaction.ispyb.data_model import (
    DataCollectionInfo,
    ExperimentType,
    ScanDataInfo,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
    StoreInIspyb,
)
from hyperion.log import ISPYB_LOGGER, set_dcgid_tag
from hyperion.parameters.constants import CONST
from hyperion.parameters.gridscan import ThreeDGridScan
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)

if TYPE_CHECKING:
    from event_model import Event, RunStart, RunStop


def ispyb_activation_wrapper(plan_generator, parameters):
    return bpp.run_wrapper(
        plan_generator,
        md={
            "activate_callbacks": ["GridscanISPyBCallback"],
            "subplan_name": CONST.PLAN.GRID_DETECT_AND_DO_GRIDSCAN,
            "hyperion_internal_parameters": (
                parameters.old_parameters()
                if isinstance(parameters, ThreeDGridScan)
                else parameters
            ).json(),
        },
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
    """

    def __init__(
        self,
        *,
        emit: Callable[..., Any] | None = None,
    ) -> None:
        super().__init__(emit=emit)
        self.params: GridscanInternalParameters
        self.ispyb: StoreInIspyb
        self.ispyb_ids: IspybIds = IspybIds()
        self._start_of_fgs_uid: str | None = None
        self._processing_start_time: float | None = None

    def activity_gated_start(self, doc: RunStart):
        if doc.get("subplan_name") == CONST.PLAN.DO_FGS:
            self._start_of_fgs_uid = doc.get("uid")
        if doc.get("subplan_name") == CONST.PLAN.GRID_DETECT_AND_DO_GRIDSCAN:
            self.uid_to_finalize_on = doc.get("uid")
            ISPYB_LOGGER.info(
                "ISPyB callback recieved start document with experiment parameters and "
                f"uid: {self.uid_to_finalize_on}"
            )
            json_params = doc.get("hyperion_internal_parameters")
            self.params = GridscanInternalParameters.from_json(json_params)
            self.ispyb = StoreInIspyb(self.ispyb_config, ExperimentType.GRIDSCAN_3D)
            data_collection_group_info = populate_data_collection_group(
                self.ispyb.experiment_type,
                self.params.hyperion_params.detector_params,
                self.params.hyperion_params.ispyb_params,
            )

            scan_data_infos = [
                ScanDataInfo(
                    data_collection_info=populate_remaining_data_collection_info(
                        None,
                        None,
                        populate_xy_data_collection_info(
                            self.params.hyperion_params.detector_params,
                        ),
                        self.params.hyperion_params.detector_params,
                        self.params.hyperion_params.ispyb_params,
                    ),
                ),
                ScanDataInfo(
                    data_collection_info=populate_remaining_data_collection_info(
                        None,
                        None,
                        populate_xz_data_collection_info(

                            self.params.hyperion_params.detector_params
                        ),
                        self.params.hyperion_params.detector_params,
                        self.params.hyperion_params.ispyb_params,
                    )
                ),
            ]

            self.ispyb_ids = self.ispyb.begin_deposition(
                data_collection_group_info, scan_data_infos
            )
            set_dcgid_tag(self.ispyb_ids.data_collection_group_id)
        return super().activity_gated_start(doc)

    def activity_gated_event(self, doc: Event):
        doc = super().activity_gated_event(doc)

        event_descriptor = self.descriptors[doc["descriptor"]]
        if event_descriptor.get("name") == ZOCALO_READING_PLAN_NAME:
            crystal_summary = ""
            if self._processing_start_time is not None:
                proc_time = time() - self._processing_start_time
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
            assert (
                self.ispyb_ids.data_collection_ids
            ), "No data collection to add results to"
            self.ispyb.append_to_comment(
                self.ispyb_ids.data_collection_ids[0], crystal_summary
            )

        return doc

    def populate_info_for_update(
        self, event_sourced_data_collection_info: DataCollectionInfo, params
    ) -> Sequence[ScanDataInfo]:
        params = cast(GridscanInternalParameters, params)
        assert (
            self.ispyb_ids.data_collection_ids
        ), "Expect at least one valid data collection to record scan data"
        xy_scan_data_info = ScanDataInfo(
            data_collection_info=event_sourced_data_collection_info,
            data_collection_position_info=populate_data_collection_position_info(
                params.hyperion_params.ispyb_params
            ),
            data_collection_id=self.ispyb_ids.data_collection_ids[0],
        )
        scan_data_infos = [xy_scan_data_info]

        data_collection_id = (
            self.ispyb_ids.data_collection_ids[1]
            if len(self.ispyb_ids.data_collection_ids) > 1
            else None
        )
        xz_scan_data_info = ScanDataInfo(
            data_collection_info=event_sourced_data_collection_info,
            data_collection_position_info=populate_data_collection_position_info(
                params.hyperion_params.ispyb_params
            ),
            data_collection_id=data_collection_id,
        )
        scan_data_infos.append(xz_scan_data_info)
        return scan_data_infos

    def activity_gated_stop(self, doc: RunStop) -> RunStop:
        if doc.get("run_start") == self._start_of_fgs_uid:
            self._processing_start_time = time()
        if doc.get("run_start") == self.uid_to_finalize_on:
            ISPYB_LOGGER.info(
                "ISPyB callback received stop document corresponding to start document "
                f"with uid: {self.uid_to_finalize_on}."
            )
            if self.ispyb_ids == IspybIds():
                raise ISPyBDepositionNotMade("ispyb was not initialised at run start")
            return super().activity_gated_stop(doc)
        return self._tag_doc(doc)
