from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Callable, Optional

from dodal.devices.aperturescatterguard import SingleAperturePosition

from hyperion.external_interaction.callbacks.common.ispyb_mapping import (
    populate_data_collection_group,
    populate_remaining_data_collection_info,
)
from hyperion.external_interaction.callbacks.ispyb_callback_base import (
    BaseISPyBCallback,
)
from hyperion.external_interaction.callbacks.rotation.ispyb_mapping import (
    populate_data_collection_info_for_rotation,
)
from hyperion.external_interaction.ispyb.data_model import (
    DataCollectionInfo,
    DataCollectionPositionInfo,
    ScanDataInfo,
)
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
    StoreInIspyb,
)
from hyperion.log import ISPYB_LOGGER, set_dcgid_tag
from hyperion.parameters.components import IspybExperimentType
from hyperion.parameters.constants import CONST
from hyperion.parameters.rotation import RotationScan

if TYPE_CHECKING:
    from event_model.documents import Event, RunStart, RunStop


class RotationIsPyBComment:
    def __init__(self):
        self.motor_position = "None"
        self.user_comment = "None"
        self.aperture_size = "None"

        # Not used yet, we need to ask scientists if it's important
        self.xrc_box = ""

    def update_comment_values(
        self, motor_pos: list[float], user_comment: str, aperture_size: str
    ) -> None:
        self.motor_position = f"({motor_pos[0]} {motor_pos[1]}, {motor_pos[2]})"
        self.user_comment = user_comment
        self.aperture_size = aperture_size

    def construct_comment(self) -> str:
        return f"Smargon XYZ positions: {self.motor_position} User comment: {self.user_comment} Aperture size: {self.aperture_size}"


class RotationISPyBCallback(BaseISPyBCallback):
    """Callback class to handle the deposition of experiment parameters into the ISPyB
    database. Listens for 'event' and 'descriptor' documents. Creates the ISpyB entry on
    recieving an 'event' document for the 'ispyb_reading_hardware' event, and updates the
    deposition on recieving its final 'stop' document.

    To use, subscribe the Bluesky RunEngine to an instance of this class.
    E.g.:
        ispyb_handler_callback = RotationISPyBCallback(parameters)
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
        self.last_sample_id: int | None = None
        self.ispyb_ids: IspybIds = IspybIds()
        self.rotation_comment: RotationIsPyBComment = RotationIsPyBComment()

    def activity_gated_start(self, doc: RunStart):
        if doc.get("subplan_name") == CONST.PLAN.ROTATION_OUTER:
            ISPYB_LOGGER.info(
                "ISPyB callback recieved start document with experiment parameters."
            )
            self.params = RotationScan.from_json(doc.get("hyperion_parameters"))
            self.rotation_comment.user_comment = self.params.comment
            dcgid = (
                self.ispyb_ids.data_collection_group_id
                if (self.params.sample_id == self.last_sample_id)
                else None
            )
            if (
                self.params.ispyb_experiment_type
                == IspybExperimentType.CHARACTERIZATION
            ):
                ISPYB_LOGGER.info("Screening collection - using new DCG")
                dcgid = None
                self.last_sample_id = None
            else:
                ISPYB_LOGGER.info(
                    f"Collection is {self.params.ispyb_experiment_type} - storing sampleID to bundle images"
                )
                self.last_sample_id = self.params.sample_id
            self.ispyb = StoreInIspyb(self.ispyb_config)
            ISPYB_LOGGER.info("Beginning ispyb deposition")
            data_collection_group_info = populate_data_collection_group(self.params)
            data_collection_info = populate_data_collection_info_for_rotation(
                self.params
            )
            data_collection_info = populate_remaining_data_collection_info(
                self.rotation_comment.construct_comment(),
                dcgid,
                data_collection_info,
                self.params,
            )
            data_collection_info.parent_id = dcgid
            scan_data_info = ScanDataInfo(
                data_collection_info=data_collection_info,
            )
            self.ispyb_ids = self.ispyb.begin_deposition(
                data_collection_group_info, [scan_data_info]
            )
        ISPYB_LOGGER.info("ISPYB handler received start document.")
        if doc.get("subplan_name") == CONST.PLAN.ROTATION_MAIN:
            self.uid_to_finalize_on = doc.get("uid")
        return super().activity_gated_start(doc)

    def populate_info_for_update(
        self,
        event_sourced_data_collection_info: DataCollectionInfo,
        event_sourced_position_info: Optional[DataCollectionPositionInfo],
        params,
    ) -> Sequence[ScanDataInfo]:
        assert (
            self.ispyb_ids.data_collection_ids
        ), "Expect an existing DataCollection to update"

        return [
            ScanDataInfo(
                data_collection_info=event_sourced_data_collection_info,
                data_collection_id=self.ispyb_ids.data_collection_ids[0],
                data_collection_position_info=event_sourced_position_info,
            )
        ]

    def _handle_ispyb_hardware_read(self, doc: Event):
        """Use the hardware read values to create the ispyb comment"""
        scan_data_infos = super()._handle_ispyb_hardware_read(doc)
        aperture_size = SingleAperturePosition(
            **doc["data"]["aperture_scatterguard-selected_aperture"]
        )
        info = scan_data_infos[0]
        assert (
            info.data_collection_position_info
        ), "Unable to find smargon motor position info"
        motor_positions = [
            info.data_collection_position_info.pos_x,
            info.data_collection_position_info.pos_y,
            info.data_collection_position_info.pos_z,
        ]
        self.rotation_comment.update_comment_values(
            motor_positions,
            self.rotation_comment.user_comment or "None",
            aperture_size.name,
        )

        scan_data_infos[0].data_collection_info.comments = (
            self.rotation_comment.construct_comment()
        )

        return scan_data_infos

    def activity_gated_event(self, doc: Event):
        doc = super().activity_gated_event(doc)
        set_dcgid_tag(self.ispyb_ids.data_collection_group_id)
        return doc

    def activity_gated_stop(self, doc: RunStop) -> RunStop:
        if doc.get("run_start") == self.uid_to_finalize_on:
            self.uid_to_finalize_on = None
            return super().activity_gated_stop(doc)
        return self._tag_doc(doc)
