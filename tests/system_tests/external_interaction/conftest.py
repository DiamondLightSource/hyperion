import os
from functools import partial
from typing import Callable

import dodal.devices.zocalo.zocalo_interaction
import ispyb.sqlalchemy
import numpy as np
import pytest
from ispyb.sqlalchemy import DataCollection
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hyperion.external_interaction.ispyb.data_model import ExperimentType
from hyperion.external_interaction.ispyb.ispyb_store import StoreInIspyb
from hyperion.parameters.constants import CONST
from hyperion.parameters.plan_specific.gridscan_internal_params import (
    GridscanInternalParameters,
)
from unit_tests.conftest import from_file as default_raw_params

TEST_RESULT_LARGE = [
    {
        "centre_of_mass": [1, 2, 3],
        "max_voxel": [1, 2, 3],
        "max_count": 105062,
        "n_voxels": 35,
        "total_count": 2387574,
        "bounding_box": [[2, 2, 2], [8, 8, 7]],
    }
]
TEST_RESULT_MEDIUM = [
    {
        "centre_of_mass": [1, 2, 3],
        "max_voxel": [2, 4, 5],
        "max_count": 105062,
        "n_voxels": 35,
        "total_count": 2387574,
        "bounding_box": [[1, 2, 3], [3, 4, 4]],
    }
]
TEST_RESULT_SMALL = [
    {
        "centre_of_mass": [1, 2, 3],
        "max_voxel": [1, 2, 3],
        "max_count": 105062,
        "n_voxels": 35,
        "total_count": 1387574,
        "bounding_box": [[2, 2, 2], [3, 3, 3]],
    }
]


def get_current_datacollection_comment(Session: Callable, dcid: int) -> str:
    """Read the 'comments' field from the given datacollection id's ISPyB entry.
    Returns an empty string if the comment is not yet initialised.
    """
    try:
        with Session() as session:
            query = session.query(DataCollection).filter(
                DataCollection.dataCollectionId == dcid
            )
            current_comment: str = query.first().comments
    except Exception:
        current_comment = ""
    return current_comment


def get_current_datacollection_attribute(
    Session: Callable, dcid: int, attr: str
) -> str:
    """Read the specified field 'attr' from the given datacollection id's ISPyB entry.
    Returns an empty string if the attribute is not found.
    """
    try:
        with Session() as session:
            query = session.query(DataCollection).filter(
                DataCollection.dataCollectionId == dcid
            )
            first_result = query.first()
            data: str = getattr(first_result, attr)
    except Exception:
        data = ""
    return data


@pytest.fixture
def fetch_comment() -> Callable:
    url = ispyb.sqlalchemy.url(CONST.SIM.DEV_ISPYB_DATABASE_CFG)
    engine = create_engine(url, connect_args={"use_pure": True})
    Session = sessionmaker(engine)
    return partial(get_current_datacollection_comment, Session)


@pytest.fixture
def fetch_datacollection_attribute() -> Callable:
    url = ispyb.sqlalchemy.url(CONST.SIM.DEV_ISPYB_DATABASE_CFG)
    engine = create_engine(url, connect_args={"use_pure": True})
    Session = sessionmaker(engine)
    return partial(get_current_datacollection_attribute, Session)


@pytest.fixture
def dummy_params():
    dummy_params = GridscanInternalParameters(**default_raw_params())
    dummy_params.hyperion_params.ispyb_params.upper_left = np.array([100, 100, 50])
    dummy_params.hyperion_params.ispyb_params.microns_per_pixel_x = 0.8
    dummy_params.hyperion_params.ispyb_params.microns_per_pixel_y = 0.8
    dummy_params.hyperion_params.ispyb_params.visit_path = (
        "/dls/i03/data/2022/cm31105-5/"
    )
    return dummy_params


@pytest.fixture
def dummy_ispyb(dummy_params) -> StoreInIspyb:
    return StoreInIspyb(CONST.SIM.DEV_ISPYB_DATABASE_CFG, ExperimentType.GRIDSCAN_2D)


@pytest.fixture
def dummy_ispyb_3d(dummy_params) -> StoreInIspyb:
    return StoreInIspyb(CONST.SIM.DEV_ISPYB_DATABASE_CFG, ExperimentType.GRIDSCAN_3D)


@pytest.fixture
def zocalo_env():
    os.environ["ZOCALO_CONFIG"] = "/dls_sw/apps/zocalo/live/configuration.yaml"
    dodal.devices.zocalo.zocalo_interaction.DEFAULT_TIMEOUT = 5
