from __future__ import annotations

import os
import re
from copy import deepcopy
from decimal import Decimal
from typing import Any, Callable, Literal, Sequence
from unittest.mock import MagicMock, patch

import numpy
import pytest
from bluesky.run_engine import RunEngine
from dodal.devices.attenuator import Attenuator
from dodal.devices.flux import Flux
from dodal.devices.s4_slit_gaps import S4SlitGaps
from dodal.devices.synchrotron import Synchrotron, SynchrotronMode
from dodal.devices.undulator import Undulator
from ophyd.status import Status
from ophyd_async.core import set_sim_value

from hyperion.experiment_plans import oav_grid_detection_plan
from hyperion.experiment_plans.grid_detect_then_xray_centre_plan import (
    GridDetectThenXRayCentreComposite,
    grid_detect_then_xray_centre,
)
from hyperion.experiment_plans.rotation_scan_plan import (
    RotationScanComposite,
    rotation_scan,
)
from hyperion.external_interaction.callbacks.common.ispyb_mapping import (
    populate_data_collection_group,
    populate_data_collection_position_info,
    populate_remaining_data_collection_info,
)
from hyperion.external_interaction.callbacks.rotation.ispyb_callback import (
    RotationISPyBCallback,
)
from hyperion.external_interaction.callbacks.xray_centre.ispyb_callback import (
    GridscanISPyBCallback,
)
from hyperion.external_interaction.callbacks.xray_centre.ispyb_mapping import (
    construct_comment_for_gridscan,
    populate_xy_data_collection_info,
    populate_xz_data_collection_info,
)
from hyperion.external_interaction.ispyb.data_model import (
    DataCollectionGridInfo,
    ExperimentType,
    ScanDataInfo,
)
from hyperion.external_interaction.ispyb.ispyb_dataclass import Orientation
from hyperion.external_interaction.ispyb.ispyb_store import (
    IspybIds,
    StoreInIspyb,
)
from hyperion.parameters.constants import CONST
from hyperion.parameters.plan_specific.grid_scan_with_edge_detect_params import (
    GridScanWithEdgeDetectInternalParameters,
)
from hyperion.parameters.plan_specific.rotation_scan_internal_params import (
    RotationInternalParameters,
)
from hyperion.utils.utils import convert_angstrom_to_eV

from ...conftest import fake_read
from .conftest import raw_params_from_file

# Map all the case-sensitive column names from their normalised versions
DATA_COLLECTION_COLUMN_MAP = {
    s.lower(): s
    for s in [
        "dataCollectionId",
        "BLSAMPLEID",
        "SESSIONID",
        "experimenttype",
        "dataCollectionNumber",
        "startTime",
        "endTime",
        "runStatus",
        "axisStart",
        "axisEnd",
        "axisRange",
        "overlap",
        "numberOfImages",
        "startImageNumber",
        "numberOfPasses",
        "exposureTime",
        "imageDirectory",
        "imagePrefix",
        "imageSuffix",
        "imageContainerSubPath",
        "fileTemplate",
        "wavelength",
        "resolution",
        "detectorDistance",
        "xBeam",
        "yBeam",
        "comments",
        "printableForReport",
        "CRYSTALCLASS",
        "slitGapVertical",
        "slitGapHorizontal",
        "transmission",
        "synchrotronMode",
        "xtalSnapshotFullPath1",
        "xtalSnapshotFullPath2",
        "xtalSnapshotFullPath3",
        "xtalSnapshotFullPath4",
        "rotationAxis",
        "phiStart",
        "kappaStart",
        "omegaStart",
        "chiStart",
        "resolutionAtCorner",
        "detector2Theta",
        "DETECTORMODE",
        "undulatorGap1",
        "undulatorGap2",
        "undulatorGap3",
        "beamSizeAtSampleX",
        "beamSizeAtSampleY",
        "centeringMethod",
        "averageTemperature",
        "ACTUALSAMPLEBARCODE",
        "ACTUALSAMPLESLOTINCONTAINER",
        "ACTUALCONTAINERBARCODE",
        "ACTUALCONTAINERSLOTINSC",
        "actualCenteringPosition",
        "beamShape",
        "dataCollectionGroupId",
        "POSITIONID",
        "detectorId",
        "FOCALSPOTSIZEATSAMPLEX",
        "POLARISATION",
        "FOCALSPOTSIZEATSAMPLEY",
        "APERTUREID",
        "screeningOrigId",
        "flux",
        "strategySubWedgeOrigId",
        "blSubSampleId",
        "processedDataFile",
        "datFullPath",
        "magnification",
        "totalAbsorbedDose",
        "binning",
        "particleDiameter",
        "boxSize",
        "minResolution",
        "minDefocus",
        "maxDefocus",
        "defocusStepSize",
        "amountAstigmatism",
        "extractSize",
        "bgRadius",
        "voltage",
        "objAperture",
        "c1aperture",
        "c2aperture",
        "c3aperture",
        "c1lens",
        "c2lens",
        "c3lens",
        "startPositionId",
        "endPositionId",
        "flux",
        "bestWilsonPlotPath",
        "totalExposedDose",
        "nominalMagnification",
        "nominalDefocus",
        "imageSizeX",
        "imageSizeY",
        "pixelSizeOnImage",
        "phasePlate",
        "dataCollectionPlanId",
    ]
}

GRID_INFO_COLUMN_MAP = {
    s.lower(): s
    for s in [
        "gridInfoId",
        "dataCollectionGroupId",
        "xOffset",
        "yOffset",
        "dx_mm",
        "dy_mm",
        "steps_x",
        "steps_y",
        "meshAngle",
        "pixelsPerMicronX",
        "pixelsPerMicronY",
        "snapshot_offsetXPixel",
        "snapshot_offsetYPixel",
        "recordTimeStamp",
        "orientation",
        "workflowMeshId",
        "snaked",
        "dataCollectionId",
        "patchesX",
        "patchesY",
        "micronsPerPixelX",
        "micronsPerPixelY",
    ]
}


@pytest.fixture
def dummy_data_collection_group_info(dummy_params):
    return populate_data_collection_group(
        ExperimentType.GRIDSCAN_2D.value,
        dummy_params.hyperion_params.detector_params,
        dummy_params.hyperion_params.ispyb_params,
    )


@pytest.fixture
def dummy_scan_data_info_for_begin(dummy_params):
    info = populate_xy_data_collection_info(
        dummy_params.hyperion_params.detector_params,
    )
    info = populate_remaining_data_collection_info(
        None,
        None,
        info,
        dummy_params.hyperion_params.detector_params,
        dummy_params.hyperion_params.ispyb_params,
    )
    return ScanDataInfo(
        data_collection_info=info,
    )


@pytest.fixture
def grid_detect_then_xray_centre_parameters():
    json_dict = raw_params_from_file(
        "tests/test_data/parameter_json_files/ispyb_gridscan_system_test_parameters.json"
    )
    return GridScanWithEdgeDetectInternalParameters(**json_dict)


# noinspection PyUnreachableCode
@pytest.fixture
def grid_detect_then_xray_centre_composite(
    fast_grid_scan,
    backlight,
    smargon,
    undulator,
    synchrotron,
    s4_slit_gaps,
    attenuator,
    xbpm_feedback,
    detector_motion,
    zocalo,
    aperture_scatterguard,
    zebra,
    eiger,
    robot,
    oav,
    dcm,
    flux,
    ophyd_pin_tip_detection,
):
    composite = GridDetectThenXRayCentreComposite(
        fast_grid_scan=fast_grid_scan,
        pin_tip_detection=ophyd_pin_tip_detection,
        backlight=backlight,
        panda_fast_grid_scan=None,  # type: ignore
        smargon=smargon,
        undulator=undulator,
        synchrotron=synchrotron,
        s4_slit_gaps=s4_slit_gaps,
        attenuator=attenuator,
        xbpm_feedback=xbpm_feedback,
        detector_motion=detector_motion,
        zocalo=zocalo,
        aperture_scatterguard=aperture_scatterguard,
        zebra=zebra,
        eiger=eiger,
        panda=None,  # type: ignore
        robot=robot,
        oav=oav,
        dcm=dcm,
        flux=flux,
    )
    eiger.odin.fan.consumers_connected.sim_put(True)
    eiger.odin.fan.on.sim_put(True)
    eiger.odin.meta.initialised.sim_put(True)
    oav.zoom_controller.zrst.set("1.0x")
    oav.cam.array_size.array_size_x.sim_put(1024)
    oav.cam.array_size.array_size_y.sim_put(768)
    oav.snapshot.x_size.sim_put(1024)
    oav.snapshot.y_size.sim_put(768)
    oav.snapshot.top_left_x.set(50)
    oav.snapshot.top_left_y.set(100)
    oav.snapshot.box_width.set(0.1 * 1000 / 1.25)  # size in pixels
    oav.snapshot.last_path_full_overlay.set("test_1_y")
    oav.snapshot.last_path_outer.set("test_2_y")
    oav.snapshot.last_saved_path.set("test_3_y")
    undulator.current_gap.sim_put(1.11)

    unpatched_method = oav.parameters.load_microns_per_pixel
    eiger.stale_params.sim_put(0)
    eiger.odin.meta.ready.sim_put(1)
    eiger.odin.fan.ready.sim_put(1)

    def patch_lmpp(zoom, xsize, ysize):
        unpatched_method(zoom, 1024, 768)

    def mock_pin_tip_detect(_):
        tip_x_px = 100
        tip_y_px = 200
        microns_per_pixel = 2.87  # from zoom levels .xml
        grid_width_px = int(400 / microns_per_pixel)
        target_grid_height_px = 70
        top_edge_data = ([0] * tip_x_px) + (
            [(tip_y_px - target_grid_height_px // 2)] * grid_width_px
        )
        bottom_edge_data = [0] * tip_x_px + [
            (tip_y_px + target_grid_height_px // 2)
        ] * grid_width_px
        ophyd_pin_tip_detection.triggered_top_edge._backend._set_value(
            numpy.array(top_edge_data, dtype=numpy.uint32)
        )

        ophyd_pin_tip_detection.triggered_bottom_edge._backend._set_value(
            numpy.array(bottom_edge_data, dtype=numpy.uint32)
        )
        yield from []
        return tip_x_px, tip_y_px

    def mock_set_file_name(val, timeout):
        eiger.odin.meta.file_name.sim_put(val)  # type: ignore
        eiger.odin.file_writer.id.sim_put(val)  # type: ignore
        return Status(success=True, done=True)

    unpatched_complete = fast_grid_scan.complete

    def mock_complete_status():
        status = unpatched_complete()
        status.set_finished()
        return status

    with (
        patch.object(eiger.odin.nodes, "get_init_state", return_value=True),
        patch.object(eiger, "wait_on_arming_if_started"),
        # xsize, ysize will always be wrong since computed as 0 before we get here
        # patch up load_microns_per_pixel connect to receive non-zero values
        patch.object(
            oav.parameters,
            "load_microns_per_pixel",
            new=MagicMock(side_effect=patch_lmpp),
        ),
        patch.object(
            oav_grid_detection_plan,
            "wait_for_tip_to_be_found",
            side_effect=mock_pin_tip_detect,
        ),
        patch.object(
            oav.snapshot, "trigger", return_value=Status(success=True, done=True)
        ),
        patch.object(
            eiger.odin.file_writer.file_name,
            "set",
            side_effect=mock_set_file_name,
        ),
        patch.object(
            fast_grid_scan, "kickoff", return_value=Status(success=True, done=True)
        ),
        patch.object(fast_grid_scan, "complete", side_effect=mock_complete_status),
        patch.object(zocalo, "trigger", return_value=Status(success=True, done=True)),
    ):
        yield composite


def scan_xy_data_info_for_update(
    data_collection_group_id, dummy_params, scan_data_info_for_begin
):
    scan_data_info_for_update = deepcopy(scan_data_info_for_begin)
    scan_data_info_for_update.data_collection_info.parent_id = data_collection_group_id
    assert dummy_params is not None
    scan_data_info_for_update.data_collection_grid_info = DataCollectionGridInfo(
        dx_in_mm=dummy_params.experiment_params.x_step_size,
        dy_in_mm=dummy_params.experiment_params.y_step_size,
        steps_x=dummy_params.experiment_params.x_steps,
        steps_y=dummy_params.experiment_params.y_steps,
        microns_per_pixel_x=1.25,
        microns_per_pixel_y=1.25,
        # cast coordinates from numpy int64 to avoid mysql type conversion issues
        snapshot_offset_x_pixel=100,
        snapshot_offset_y_pixel=100,
        orientation=Orientation.HORIZONTAL,
        snaked=True,
    )
    scan_data_info_for_update.data_collection_info.comments = (
        construct_comment_for_gridscan(
            scan_data_info_for_update.data_collection_grid_info,
        )
    )
    scan_data_info_for_update.data_collection_position_info = (
        populate_data_collection_position_info(
            dummy_params.hyperion_params.ispyb_params
        )
    )
    return scan_data_info_for_update


def scan_data_infos_for_update_3d(
    ispyb_ids, scan_xy_data_info_for_update, dummy_params
):
    xz_data_collection_info = populate_xz_data_collection_info(
        dummy_params.hyperion_params.detector_params
    )

    assert dummy_params.hyperion_params.ispyb_params is not None
    assert dummy_params is not None
    data_collection_grid_info = DataCollectionGridInfo(
        dx_in_mm=dummy_params.experiment_params.x_step_size,
        dy_in_mm=dummy_params.experiment_params.z_step_size,
        steps_x=dummy_params.experiment_params.x_steps,
        steps_y=dummy_params.experiment_params.z_steps,
        microns_per_pixel_x=1.25,
        microns_per_pixel_y=1.25,
        # cast coordinates from numpy int64 to avoid mysql type conversion issues
        snapshot_offset_x_pixel=100,
        snapshot_offset_y_pixel=50,
        orientation=Orientation.HORIZONTAL,
        snaked=True,
    )
    xz_data_collection_info = populate_remaining_data_collection_info(
        construct_comment_for_gridscan(data_collection_grid_info),
        ispyb_ids.data_collection_group_id,
        xz_data_collection_info,
        dummy_params.hyperion_params.detector_params,
        dummy_params.hyperion_params.ispyb_params,
    )
    xz_data_collection_info.parent_id = ispyb_ids.data_collection_group_id

    scan_xz_data_info_for_update = ScanDataInfo(
        data_collection_info=xz_data_collection_info,
        data_collection_grid_info=(data_collection_grid_info),
        data_collection_position_info=(
            populate_data_collection_position_info(
                dummy_params.hyperion_params.ispyb_params
            )
        ),
    )
    return [scan_xy_data_info_for_update, scan_xz_data_info_for_update]


@pytest.mark.s03
def test_ispyb_get_comment_from_collection_correctly(fetch_comment: Callable[..., Any]):
    expected_comment_contents = (
        "Xray centring - "
        "Diffraction grid scan of 1 by 41 images, "
        "Top left [454,-4], Bottom right [455,772]"
    )

    assert fetch_comment(8292317) == expected_comment_contents

    assert fetch_comment(2) == ""


@pytest.mark.s03
def test_ispyb_deposition_comment_correct_on_failure(
    dummy_ispyb: StoreInIspyb,
    fetch_comment: Callable[..., Any],
    dummy_params,
    dummy_data_collection_group_info,
    dummy_scan_data_info_for_begin,
):
    ispyb_ids = dummy_ispyb.begin_deposition(
        dummy_data_collection_group_info, [dummy_scan_data_info_for_begin]
    )
    dummy_ispyb.end_deposition(ispyb_ids, "fail", "could not connect to devices")
    assert (
        fetch_comment(ispyb_ids.data_collection_ids[0])  # type: ignore
        == "DataCollection Unsuccessful reason: could not connect to devices"
    )


@pytest.mark.s03
def test_ispyb_deposition_comment_correct_for_3D_on_failure(
    dummy_ispyb_3d: StoreInIspyb,
    fetch_comment: Callable[..., Any],
    dummy_params,
    dummy_data_collection_group_info,
    dummy_scan_data_info_for_begin,
):
    ispyb_ids = dummy_ispyb_3d.begin_deposition(
        dummy_data_collection_group_info, [dummy_scan_data_info_for_begin]
    )
    scan_data_infos = generate_scan_data_infos(
        dummy_params,
        dummy_scan_data_info_for_begin,
        ExperimentType.GRIDSCAN_3D,
        ispyb_ids,
    )
    ispyb_ids = dummy_ispyb_3d.update_deposition(
        ispyb_ids, dummy_data_collection_group_info, scan_data_infos
    )
    dcid1 = ispyb_ids.data_collection_ids[0]  # type: ignore
    dcid2 = ispyb_ids.data_collection_ids[1]  # type: ignore
    dummy_ispyb_3d.end_deposition(ispyb_ids, "fail", "could not connect to devices")
    assert (
        fetch_comment(dcid1)
        == "Hyperion: Xray centring - Diffraction grid scan of 40 by 20 images in 100.0 um by 100.0 um steps. Top left (px): [100,100], bottom right (px): [3300,1700]. DataCollection Unsuccessful reason: could not connect to devices"
    )
    assert (
        fetch_comment(dcid2)
        == "Hyperion: Xray centring - Diffraction grid scan of 40 by 10 images in 100.0 um by 100.0 um steps. Top left (px): [100,50], bottom right (px): [3300,850]. DataCollection Unsuccessful reason: could not connect to devices"
    )


@pytest.mark.s03
@pytest.mark.parametrize(
    "experiment_type, exp_num_of_grids, success",
    [
        (ExperimentType.GRIDSCAN_2D, 1, False),
        (ExperimentType.GRIDSCAN_2D, 1, True),
        (ExperimentType.GRIDSCAN_3D, 2, False),
        (ExperimentType.GRIDSCAN_3D, 2, True),
    ],
)
def test_can_store_2D_ispyb_data_correctly_when_in_error(
    experiment_type,
    exp_num_of_grids: Literal[1, 2],
    success: bool,
    fetch_comment: Callable[..., Any],
    dummy_params,
    dummy_data_collection_group_info,
    dummy_scan_data_info_for_begin,
):
    ispyb: StoreInIspyb = StoreInIspyb(
        CONST.SIM.DEV_ISPYB_DATABASE_CFG, experiment_type
    )
    ispyb_ids: IspybIds = ispyb.begin_deposition(
        dummy_data_collection_group_info, [dummy_scan_data_info_for_begin]
    )
    scan_data_infos = generate_scan_data_infos(
        dummy_params, dummy_scan_data_info_for_begin, experiment_type, ispyb_ids
    )

    ispyb_ids = ispyb.update_deposition(
        ispyb_ids, dummy_data_collection_group_info, scan_data_infos
    )
    assert len(ispyb_ids.data_collection_ids) == exp_num_of_grids  # type: ignore
    assert len(ispyb_ids.grid_ids) == exp_num_of_grids  # type: ignore
    assert isinstance(ispyb_ids.data_collection_group_id, int)

    expected_comments = [
        (
            "Hyperion: Xray centring - Diffraction grid scan of 40 by 20 "
            "images in 100.0 um by 100.0 um steps. Top left (px): [100,100], bottom right (px): [3300,1700]."
        ),
        (
            "Hyperion: Xray centring - Diffraction grid scan of 40 by 10 "
            "images in 100.0 um by 100.0 um steps. Top left (px): [100,50], bottom right (px): [3300,850]."
        ),
    ]

    if success:
        ispyb.end_deposition(ispyb_ids, "success", "")
    else:
        ispyb.end_deposition(ispyb_ids, "fail", "In error")
        expected_comments = [
            e + " DataCollection Unsuccessful reason: In error"
            for e in expected_comments
        ]

    assert (
        not isinstance(ispyb_ids.data_collection_ids, int)
        and ispyb_ids.data_collection_ids is not None
    )
    for grid_no, dc_id in enumerate(ispyb_ids.data_collection_ids):
        assert fetch_comment(dc_id) == expected_comments[grid_no]


def generate_scan_data_infos(
    dummy_params,
    dummy_scan_data_info_for_begin: ScanDataInfo,
    experiment_type: ExperimentType,
    ispyb_ids: IspybIds,
) -> Sequence[ScanDataInfo]:
    xy_scan_data_info = scan_xy_data_info_for_update(
        ispyb_ids.data_collection_group_id, dummy_params, dummy_scan_data_info_for_begin
    )
    xy_scan_data_info.data_collection_id = ispyb_ids.data_collection_ids[0]
    if experiment_type == ExperimentType.GRIDSCAN_3D:
        scan_data_infos = scan_data_infos_for_update_3d(
            ispyb_ids, xy_scan_data_info, dummy_params
        )
    else:
        scan_data_infos = [xy_scan_data_info]
    return scan_data_infos


@pytest.mark.s03
def test_ispyb_deposition_in_gridscan(
    RE: RunEngine,
    grid_detect_then_xray_centre_composite: GridDetectThenXRayCentreComposite,
    grid_detect_then_xray_centre_parameters: GridScanWithEdgeDetectInternalParameters,
    fetch_datacollection_attribute: Callable[..., Any],
    fetch_datacollection_grid_attribute: Callable[..., Any],
    fetch_datacollection_position_attribute: Callable[..., Any],
):
    os.environ["ISPYB_CONFIG_PATH"] = CONST.SIM.DEV_ISPYB_DATABASE_CFG
    grid_detect_then_xray_centre_composite.s4_slit_gaps.xgap.user_readback.sim_put(0.1)
    grid_detect_then_xray_centre_composite.s4_slit_gaps.ygap.user_readback.sim_put(0.1)
    ispyb_callback = GridscanISPyBCallback()
    RE.subscribe(ispyb_callback)
    RE(
        grid_detect_then_xray_centre(
            grid_detect_then_xray_centre_composite,
            grid_detect_then_xray_centre_parameters,
        )
    )

    ispyb_ids = ispyb_callback.ispyb_ids
    expected_values = {
        "detectorid": 78,
        "axisstart": 0.0,
        "axisrange": 0,
        "axisend": 0,
        "focalspotsizeatsamplex": 1.0,
        "focalspotsizeatsampley": 1.0,
        "slitgapvertical": 0.1,
        "slitgaphorizontal": 0.1,
        "beamsizeatsamplex": 1,
        "beamsizeatsampley": 1,
        "transmission": 49.118,
        "datacollectionnumber": 0,
        "detectordistance": 100.0,
        "exposuretime": 0.12,
        "imagedirectory": "/tmp/",
        "imageprefix": "file_name",
        "imagesuffix": "h5",
        "numberofpasses": 1,
        "overlap": 0,
        "omegastart": 0,
        "startimagenumber": 1,
        "resolution": 1.0,
        "wavelength": 0.976254,
        "xbeam": 150.0,
        "ybeam": 160.0,
        "xtalsnapshotfullpath1": "test_1_y",
        "xtalsnapshotfullpath2": "test_2_y",
        "xtalsnapshotfullpath3": "test_3_y",
        "synchrotronmode": "User",
        "undulatorgap1": 1.11,
        "filetemplate": "file_name_0_master.h5",
        "numberofimages": 20 * 12,
    }
    compare_comment(
        fetch_datacollection_attribute,
        ispyb_ids.data_collection_ids[0],
        "Hyperion: Xray centring - Diffraction grid scan of 20 by 12 "
        "images in 20.0 um by 20.0 um steps. Top left (px): [100,161], "
        "bottom right (px): [239,244].",
    )
    compare_actual_and_expected(
        ispyb_ids.data_collection_ids[0],
        expected_values,
        fetch_datacollection_attribute,
        DATA_COLLECTION_COLUMN_MAP,
    )
    expected_values = {
        "gridInfoId": ispyb_ids.grid_ids[0],
        "dx_mm": 0.02,
        "dy_mm": 0.02,
        "steps_x": 20,
        "steps_y": 12,
        "snapshot_offsetXPixel": 100,
        "snapshot_offsetYPixel": 161,
        "orientation": "horizontal",
        "snaked": True,
        "dataCollectionId": ispyb_ids.data_collection_ids[0],
        "micronsPerPixelX": 2.87,
        "micronsPerPixelY": 2.87,
    }

    compare_actual_and_expected(
        ispyb_ids.grid_ids[0],
        expected_values,
        fetch_datacollection_grid_attribute,
        GRID_INFO_COLUMN_MAP,
    )
    position_id = fetch_datacollection_attribute(
        ispyb_ids.data_collection_ids[0], DATA_COLLECTION_COLUMN_MAP["positionid"]
    )
    expected_values = {"posX": 10.0, "posY": 20.0, "posZ": 30.0}
    compare_actual_and_expected(
        position_id, expected_values, fetch_datacollection_position_attribute
    )
    expected_values = {
        "detectorid": 78,
        "axisstart": 90.0,
        "axisrange": 0,
        "axisend": 90,
        "focalspotsizeatsamplex": 1.0,
        "focalspotsizeatsampley": 1.0,
        "slitgapvertical": 0.1,
        "slitgaphorizontal": 0.1,
        "beamsizeatsamplex": 1,
        "beamsizeatsampley": 1,
        "transmission": 49.118,
        "datacollectionnumber": 1,
        "detectordistance": 100.0,
        "exposuretime": 0.12,
        "imagedirectory": "/tmp/",
        "imageprefix": "file_name",
        "imagesuffix": "h5",
        "numberofpasses": 1,
        "overlap": 0,
        "omegastart": 90,
        "startimagenumber": 1,
        "resolution": 1.0,
        "wavelength": 0.976254,
        "xbeam": 150.0,
        "ybeam": 160.0,
        "xtalsnapshotfullpath1": "test_1_y",
        "xtalsnapshotfullpath2": "test_2_y",
        "xtalsnapshotfullpath3": "test_3_y",
        "synchrotronmode": "User",
        "undulatorgap1": 1.11,
        "filetemplate": "file_name_1_master.h5",
        "numberofimages": 20 * 11,
    }
    compare_actual_and_expected(
        ispyb_ids.data_collection_ids[1],
        expected_values,
        fetch_datacollection_attribute,
        DATA_COLLECTION_COLUMN_MAP,
    )
    compare_comment(
        fetch_datacollection_attribute,
        ispyb_ids.data_collection_ids[1],
        "Hyperion: Xray centring - Diffraction grid scan of 20 by 11 "
        "images in 20.0 um by 20.0 um steps. Top left (px): [100,165], "
        "bottom right (px): [239,241].",
    )
    position_id = fetch_datacollection_attribute(
        ispyb_ids.data_collection_ids[1], DATA_COLLECTION_COLUMN_MAP["positionid"]
    )
    expected_values = {"posX": 10.0, "posY": 20.0, "posZ": 30.0}
    compare_actual_and_expected(
        position_id, expected_values, fetch_datacollection_position_attribute
    )
    expected_values = {
        "gridInfoId": ispyb_ids.grid_ids[1],
        "dx_mm": 0.02,
        "dy_mm": 0.02,
        "steps_x": 20,
        "steps_y": 11,
        "snapshot_offsetXPixel": 100,
        "snapshot_offsetYPixel": 165,
        "orientation": "horizontal",
        "snaked": True,
        "dataCollectionId": ispyb_ids.data_collection_ids[1],
        "micronsPerPixelX": 2.87,
        "micronsPerPixelY": 2.87,
    }
    compare_actual_and_expected(
        ispyb_ids.grid_ids[1],
        expected_values,
        fetch_datacollection_grid_attribute,
        GRID_INFO_COLUMN_MAP,
    )


def compare_comment(
    fetch_datacollection_attribute, data_collection_id, expected_comment
):
    actual_comment = fetch_datacollection_attribute(
        data_collection_id, DATA_COLLECTION_COLUMN_MAP["comments"]
    )
    match = re.search(" Zocalo processing took", actual_comment)
    truncated_comment = actual_comment[: match.start()] if match else actual_comment
    assert truncated_comment == expected_comment


def compare_actual_and_expected(
    id, expected_values, fetch_datacollection_attribute, column_map: dict | None = None
):
    for k, v in expected_values.items():
        actual = fetch_datacollection_attribute(
            id, column_map[k.lower()] if column_map else k
        )
        if isinstance(actual, Decimal):
            actual = float(actual)
        if isinstance(v, float):
            actual_v = actual == pytest.approx(v)
        else:
            actual_v = actual == v  # if this is inlined, I don't get a nice message :/
        assert actual_v, f"expected {k} {v} == {actual}"


@pytest.mark.s03
@patch("bluesky.plan_stubs.wait")
def test_ispyb_deposition_in_rotation_plan(
    bps_wait,
    fake_create_rotation_devices: RotationScanComposite,
    RE: RunEngine,
    test_rotation_params: RotationInternalParameters,
    fetch_comment: Callable[..., Any],
    fetch_datacollection_attribute: Callable[..., Any],
    fetch_datacollectiongroup_attribute: Callable[..., Any],
    undulator: Undulator,
    attenuator: Attenuator,
    synchrotron: Synchrotron,
    s4_slit_gaps: S4SlitGaps,
    flux: Flux,
    robot,
    fake_create_devices: dict[str, Any],
):
    test_wl = 0.71
    test_bs_x = 0.023
    test_bs_y = 0.047
    test_exp_time = 0.023
    test_img_wid = 0.27
    test_undulator_current_gap = 1.12
    test_synchrotron_mode = SynchrotronMode.USER
    test_slit_gap_horiz = 0.123
    test_slit_gap_vert = 0.234

    test_rotation_params.experiment_params.image_width = test_img_wid
    test_rotation_params.hyperion_params.ispyb_params.beam_size_x = test_bs_x
    test_rotation_params.hyperion_params.ispyb_params.beam_size_y = test_bs_y
    test_rotation_params.hyperion_params.detector_params.exposure_time = test_exp_time
    energy_ev = convert_angstrom_to_eV(test_wl)
    fake_create_rotation_devices.dcm.energy_in_kev.user_readback.sim_put(  # pyright: ignore
        energy_ev / 1000
    )
    fake_create_rotation_devices.undulator.current_gap.sim_put(1.12)  # pyright: ignore
    set_sim_value(
        fake_create_rotation_devices.synchrotron.synchrotron_mode,
        test_synchrotron_mode,
    )
    set_sim_value(
        fake_create_rotation_devices.synchrotron.topup_start_countdown,  # pyright: ignore
        -1,
    )
    fake_create_rotation_devices.s4_slit_gaps.xgap.user_readback.sim_put(  # pyright: ignore
        test_slit_gap_horiz
    )
    fake_create_rotation_devices.s4_slit_gaps.ygap.user_readback.sim_put(  # pyright: ignore
        test_slit_gap_vert
    )
    test_rotation_params.hyperion_params.detector_params.expected_energy_ev = energy_ev

    os.environ["ISPYB_CONFIG_PATH"] = CONST.SIM.DEV_ISPYB_DATABASE_CFG
    ispyb_cb = RotationISPyBCallback()
    RE.subscribe(ispyb_cb)

    composite = RotationScanComposite(
        attenuator=attenuator,
        backlight=fake_create_devices["backlight"],
        dcm=fake_create_rotation_devices.dcm,
        detector_motion=fake_create_devices["detector_motion"],
        eiger=fake_create_devices["eiger"],
        flux=flux,
        smargon=fake_create_devices["smargon"],
        undulator=undulator,
        synchrotron=synchrotron,
        s4_slit_gaps=s4_slit_gaps,
        zebra=fake_create_devices["zebra"],
        aperture_scatterguard=fake_create_devices["ap_sg"],
        robot=robot,
    )

    with patch("bluesky.preprocessors.__read_and_stash_a_motor", fake_read):
        RE(
            rotation_scan(
                composite,
                test_rotation_params,
            )
        )

    dcid = ispyb_cb.ispyb_ids.data_collection_ids[0]
    assert dcid is not None
    assert fetch_comment(dcid) == "Hyperion rotation scan"
    assert fetch_datacollection_attribute(dcid, "wavelength") == test_wl
    assert fetch_datacollection_attribute(dcid, "beamSizeAtSampleX") == test_bs_x
    assert fetch_datacollection_attribute(dcid, "beamSizeAtSampleY") == test_bs_y
    assert fetch_datacollection_attribute(dcid, "exposureTime") == test_exp_time
    assert (
        fetch_datacollection_attribute(dcid, "undulatorGap1")
        == test_undulator_current_gap
    )
    assert (
        fetch_datacollection_attribute(dcid, "synchrotronMode")
        == test_synchrotron_mode.value
    )
    assert (
        fetch_datacollection_attribute(dcid, "slitGapHorizontal") == test_slit_gap_horiz
    )
    assert fetch_datacollection_attribute(dcid, "slitGapVertical") == test_slit_gap_vert
    # TODO Can't test barcode as need BLSample which needs Dewar, Shipping, Container entries for the
    # upsert stored proc to use it.
