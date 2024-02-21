from __future__ import annotations

from time import time
from typing import TYPE_CHECKING

import numpy as np
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
    construct_comment_for_gridscan,
    populate_data_collection_grid_info,
    populate_xy_data_collection_info,
    populate_xz_data_collection_info,
)
from hyperion.external_interaction.exceptions import ISPyBDepositionNotMade
from hyperion.external_interaction.ispyb.data_model import GridScanInfo, ScanDataInfo
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
from hyperion.parameters.constants import GRIDSCAN_OUTER_PLAN
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

    def __init__(self) -> None:
        super().__init__()
        self.params: GridscanInternalParameters
        self.ispyb: StoreGridscanInIspyb
        self.ispyb_ids: IspybIds = IspybIds()
        self.processing_start_time: float | None = None

    def is_3d_gridscan(self):
        return self.params.experiment_params.is_3d_grid_scan

    def activity_gated_start(self, doc: RunStart):
        if doc.get("subplan_name") == GRIDSCAN_OUTER_PLAN:
            self.uid_to_finalize_on = doc.get("uid")
            ISPYB_LOGGER.info(
                "ISPyB callback recieved start document with experiment parameters and "
                f"uid: {self.uid_to_finalize_on}"
            )
            json_params = doc.get("hyperion_internal_parameters")
            self.params = GridscanInternalParameters.from_json(json_params)
            self.ispyb = (
                Store3DGridscanInIspyb(self.ispyb_config)
                if self.is_3d_gridscan()
                else Store2DGridscanInIspyb(self.ispyb_config)
            )
            data_collection_group_info = populate_data_collection_group(
                self.ispyb.experiment_type,
                self.params.hyperion_params.detector_params,
                self.params.hyperion_params.ispyb_params,
            )
            grid_scan_info = GridScanInfo(
                self.params.hyperion_params.ispyb_params.upper_left,
                self.params.experiment_params.y_steps,
                self.params.experiment_params.y_step_size,
            )

            def constructor():
                return construct_comment_for_gridscan(
                    self.params,
                    self.params.hyperion_params.ispyb_params,
                    grid_scan_info,
                )

            scan_data_info = ScanDataInfo(
                data_collection_info=populate_remaining_data_collection_info(
                    constructor,
                    None,
                    populate_xy_data_collection_info(
                        grid_scan_info,
                        self.params,
                        self.params.hyperion_params.ispyb_params,
                        self.params.hyperion_params.detector_params,
                    ),
                    self.params.hyperion_params.detector_params,
                    self.params.hyperion_params.ispyb_params,
                ),
            )
            self.ispyb_ids = self.ispyb.begin_deposition(
                data_collection_group_info, scan_data_info
            )
            set_dcgid_tag(self.ispyb_ids.data_collection_group_id)

    def activity_gated_event(self, doc: Event):
        doc = super().activity_gated_event(doc)

        event_descriptor = self.descriptors[doc["descriptor"]]
        if event_descriptor.get("name") == ZOCALO_READING_PLAN_NAME:
            crystal_summary = ""
            if self.processing_start_time is not None:
                proc_time = time() - self.processing_start_time
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
            assert isinstance(self.ispyb_ids.data_collection_ids, tuple)
            self.ispyb.append_to_comment(
                self.ispyb_ids.data_collection_ids[0], crystal_summary
            )

        return doc

    def update_deposition(self, params):
        data_collection_group_info = populate_data_collection_group(
            self.ispyb.experiment_type,
            params.hyperion_params.detector_params,
            params.hyperion_params.ispyb_params,
        )

        scan_data_infos = [self.populate_xy_scan_data_info(params)]
        if self.is_3d_gridscan():
            scan_data_infos.append(self.populate_xz_scan_data_info(params))

        return self.ispyb.update_deposition(
            params, data_collection_group_info, scan_data_infos
        )

    def populate_xy_scan_data_info(self, params):
        grid_scan_info = GridScanInfo(
            [
                int(params.hyperion_params.ispyb_params.upper_left[0]),
                int(params.hyperion_params.ispyb_params.upper_left[1]),
            ],
            params.experiment_params.y_steps,
            params.experiment_params.y_step_size,
        )

        xy_data_collection_info = populate_xy_data_collection_info(
            grid_scan_info,
            params,
            params.hyperion_params.ispyb_params,
            params.hyperion_params.detector_params,
        )

        def comment_constructor():
            return construct_comment_for_gridscan(
                params, params.hyperion_params.ispyb_params, grid_scan_info
            )

        xy_data_collection_info = populate_remaining_data_collection_info(
            comment_constructor,
            self.ispyb_ids.data_collection_group_id,
            xy_data_collection_info,
            params.hyperion_params.detector_params,
            params.hyperion_params.ispyb_params,
        )

        return ScanDataInfo(
            data_collection_info=xy_data_collection_info,
            data_collection_grid_info=populate_data_collection_grid_info(
                params, grid_scan_info, params.hyperion_params.ispyb_params
            ),
            data_collection_position_info=populate_data_collection_position_info(
                params.hyperion_params.ispyb_params
            ),
        )

    def populate_xz_scan_data_info(self, params):
        xz_grid_scan_info = GridScanInfo(
            [
                int(params.hyperion_params.ispyb_params.upper_left[0]),
                int(params.hyperion_params.ispyb_params.upper_left[2]),
            ],
            params.experiment_params.z_steps,
            params.experiment_params.z_step_size,
        )
        xz_data_collection_info = populate_xz_data_collection_info(
            xz_grid_scan_info,
            params,
            params.hyperion_params.ispyb_params,
            params.hyperion_params.detector_params,
        )

        def xz_comment_constructor():
            return construct_comment_for_gridscan(
                params, params.hyperion_params.ispyb_params, xz_grid_scan_info
            )

        xz_data_collection_info = populate_remaining_data_collection_info(
            xz_comment_constructor,
            self.ispyb_ids.data_collection_group_id,
            xz_data_collection_info,
            params.hyperion_params.detector_params,
            params.hyperion_params.ispyb_params,
        )
        return ScanDataInfo(
            data_collection_info=xz_data_collection_info,
            data_collection_grid_info=populate_data_collection_grid_info(
                params, xz_grid_scan_info, params.hyperion_params.ispyb_params
            ),
            data_collection_position_info=populate_data_collection_position_info(
                params.hyperion_params.ispyb_params
            ),
        )

    def activity_gated_stop(self, doc: RunStop):
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
