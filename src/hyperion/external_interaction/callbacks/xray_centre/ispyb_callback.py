from __future__ import annotations

from collections.abc import Sequence
from time import time
from typing import TYPE_CHECKING, Any, Callable, List, Optional

import numpy as np
from blueapi.core import MsgGenerator
from bluesky import preprocessors as bpp
from dodal.devices.zocalo.zocalo_results import ZOCALO_READING_PLAN_NAME

from hyperion.external_interaction.callbacks.common.ispyb_mapping import (
    populate_data_collection_group,
    populate_remaining_data_collection_info,
)
from hyperion.external_interaction.callbacks.ispyb_callback_base import (
    BaseISPyBCallback,
)
from hyperion.external_interaction.callbacks.logging_callback import format_doc_for_log
from hyperion.external_interaction.callbacks.xray_centre.ispyb_mapping import (
    construct_comment_for_gridscan,
    populate_xy_data_collection_info,
    populate_xz_data_collection_info,
)
from hyperion.external_interaction.exceptions import ISPyBDepositionNotMade
from hyperion.external_interaction.ispyb.data_model import (
    DataCollectionGridInfo,
    DataCollectionInfo,
    DataCollectionPositionInfo,
    ScanDataInfo,
)
from hyperion.external_interaction.ispyb.ispyb_dataclass import Orientation
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
    StoreInIspyb,
)
from hyperion.log import ISPYB_LOGGER, set_dcgid_tag
from hyperion.parameters.components import DiffractionExperimentWithSample
from hyperion.parameters.constants import CONST
from hyperion.parameters.gridscan import (
    GridCommon,
)

if TYPE_CHECKING:
    from event_model import Event, RunStart, RunStop


def ispyb_activation_wrapper(plan_generator: MsgGenerator, parameters):
    return bpp.run_wrapper(
        plan_generator,
        md={
            "activate_callbacks": ["GridscanISPyBCallback"],
            "subplan_name": CONST.PLAN.GRID_DETECT_AND_DO_GRIDSCAN,
            "hyperion_parameters": parameters.json(),
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
                "ISPyB callback received start document with experiment parameters and "
                f"uid: {self.uid_to_finalize_on}"
            )
            self.params = GridCommon.from_json(
                doc.get("hyperion_parameters"), allow_extras=True
            )
            self.ispyb = StoreInIspyb(self.ispyb_config)
            data_collection_group_info = populate_data_collection_group(self.params)

            scan_data_infos = [
                ScanDataInfo(
                    data_collection_info=populate_remaining_data_collection_info(
                        None,
                        None,
                        populate_xy_data_collection_info(
                            self.params.detector_params,
                        ),
                        self.params,
                    ),
                ),
                ScanDataInfo(
                    data_collection_info=populate_remaining_data_collection_info(
                        None,
                        None,
                        populate_xz_data_collection_info(self.params.detector_params),
                        self.params,
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

        descriptor_name = self.descriptors[doc["descriptor"]].get("name")
        if descriptor_name == ZOCALO_READING_PLAN_NAME:
            self._handle_zocalo_read_event(doc)
        elif descriptor_name == CONST.DESCRIPTORS.OAV_GRID_SNAPSHOT_TRIGGERED:
            scan_data_infos = self._handle_oav_grid_snapshot_triggered(doc)
            self.ispyb_ids = self.ispyb.update_deposition(
                self.ispyb_ids, scan_data_infos
            )

        return doc

    def _handle_zocalo_read_event(self, doc):
        crystal_summary = ""
        if self._processing_start_time is not None:
            proc_time = time() - self._processing_start_time
            crystal_summary = f"Zocalo processing took {proc_time:.2f} s. "
        bboxes: List[np.ndarray] = []
        ISPYB_LOGGER.info(
            f"Amending comment based on Zocalo reading doc: {format_doc_for_log(doc)}"
        )
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

    def _handle_oav_grid_snapshot_triggered(self, doc) -> Sequence[ScanDataInfo]:
        assert self.ispyb_ids.data_collection_ids, "No current data collection"
        assert self.params, "ISPyB handler didn't receive parameters!"
        data = doc["data"]
        data_collection_id = None
        data_collection_info = DataCollectionInfo(
            xtal_snapshot1=data.get("oav_grid_snapshot_last_path_full_overlay"),
            xtal_snapshot2=data.get("oav_grid_snapshot_last_path_outer"),
            xtal_snapshot3=data.get("oav_grid_snapshot_last_saved_path"),
            n_images=(
                data["oav_grid_snapshot_num_boxes_x"]
                * data["oav_grid_snapshot_num_boxes_y"]
            ),
        )
        microns_per_pixel_x = data["oav_grid_snapshot_microns_per_pixel_x"]
        microns_per_pixel_y = data["oav_grid_snapshot_microns_per_pixel_y"]
        data_collection_grid_info = DataCollectionGridInfo(
            dx_in_mm=data["oav_grid_snapshot_box_width"] * microns_per_pixel_x / 1000,
            dy_in_mm=data["oav_grid_snapshot_box_width"] * microns_per_pixel_y / 1000,
            steps_x=data["oav_grid_snapshot_num_boxes_x"],
            steps_y=data["oav_grid_snapshot_num_boxes_y"],
            microns_per_pixel_x=microns_per_pixel_x,
            microns_per_pixel_y=microns_per_pixel_y,
            snapshot_offset_x_pixel=int(data["oav_grid_snapshot_top_left_x"]),
            snapshot_offset_y_pixel=int(data["oav_grid_snapshot_top_left_y"]),
            orientation=Orientation.HORIZONTAL,
            snaked=True,
        )
        data_collection_info.comments = construct_comment_for_gridscan(
            data_collection_grid_info
        )
        if len(self.ispyb_ids.data_collection_ids) > self._oav_snapshot_event_idx:
            data_collection_id = self.ispyb_ids.data_collection_ids[
                self._oav_snapshot_event_idx
            ]
        self._populate_axis_info(data_collection_info, doc["data"]["smargon-omega"])

        scan_data_info = ScanDataInfo(
            data_collection_info=data_collection_info,
            data_collection_id=data_collection_id,
            data_collection_grid_info=data_collection_grid_info,
        )
        ISPYB_LOGGER.info("Updating ispyb data collection after oav snapshot.")
        self._oav_snapshot_event_idx += 1
        return [scan_data_info]

    def _populate_axis_info(
        self, data_collection_info: DataCollectionInfo, omega_start: float | None
    ):
        if omega_start is not None:
            omega_in_gda_space = -omega_start
            data_collection_info.omega_start = omega_in_gda_space
            data_collection_info.axis_start = omega_in_gda_space
            data_collection_info.axis_end = omega_in_gda_space
            data_collection_info.axis_range = 0

    def populate_info_for_update(
        self,
        event_sourced_data_collection_info: DataCollectionInfo,
        event_sourced_position_info: Optional[DataCollectionPositionInfo],
        params: DiffractionExperimentWithSample,
    ) -> Sequence[ScanDataInfo]:
        assert (
            self.ispyb_ids.data_collection_ids
        ), "Expect at least one valid data collection to record scan data"
        xy_scan_data_info = ScanDataInfo(
            data_collection_info=event_sourced_data_collection_info,
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
