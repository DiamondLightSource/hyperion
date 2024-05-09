import os
from time import sleep

import pytest
from requests import get

from hyperion.external_interaction.ispyb.exp_eye_store import ExpeyeInteraction
from hyperion.parameters.constants import CONST


@pytest.mark.s03
def test_start_and_end_robot_load():
    """To confirm this test is successful go to
    https://ispyb-test.diamond.ac.uk/dc/visit/cm37235-2 and see that data is added
    when it's run.
    """
    os.environ["ISPYB_CONFIG_PATH"] = CONST.SIM.DEV_ISPYB_DATABASE_CFG

    SAMPLE_ID = "5289780"
    BARCODE = "test_barcode"

    expeye = ExpeyeInteraction()

    robot_action_id = expeye.start_load("cm37235", 2, SAMPLE_ID, 40, 3)

    sleep(0.5)

    print(f"Created {robot_action_id}")

    test_folder = "/dls/i03/data/2024/cm37235-2/xtal_snapshots"
    oav_snapshot = test_folder + "/235855_load_after_0.0.png"
    webcam_snapshot = test_folder + "/235855_webcam.jpg"
    expeye.update_barcode_and_snapshots(
        robot_action_id, BARCODE, oav_snapshot, webcam_snapshot
    )

    sleep(0.5)

    expeye.end_load(robot_action_id, "fail", "Oh no!")

    get_robot_data_url = f"{expeye.base_url}/robot-actions/{robot_action_id}"
    response = get(get_robot_data_url, auth=expeye.auth)

    assert response.ok

    response = response.json()
    assert response["robotActionId"] == robot_action_id
    assert response["status"] == "ERROR"
    assert response["sampleId"] == SAMPLE_ID
    assert response["sampleBarcode"] == BARCODE
