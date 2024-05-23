import os
from functools import partial
from typing import Any, Callable

import ispyb.sqlalchemy
import pytest
from ispyb.sqlalchemy import DataCollection, DataCollectionGroup, GridInfo, Position
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hyperion.external_interaction.ispyb.ispyb_store import StoreInIspyb
from hyperion.parameters.constants import CONST
from hyperion.parameters.gridscan import ThreeDGridScan

from ...conftest import raw_params_from_file

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


def get_current_datacollection_grid_attribute(
    Session: Callable, grid_id: int, attr: str
) -> Any:
    with Session() as session:
        query = session.query(GridInfo).filter(GridInfo.gridInfoId == grid_id)
        first_result = query.first()
        return getattr(first_result, attr)


def get_current_position_attribute(
    Session: Callable, position_id: int, attr: str
) -> Any:
    with Session() as session:
        query = session.query(Position).filter(Position.positionId == position_id)
        first_result = query.first()
        if first_result is None:
            return None
        return getattr(first_result, attr)


def get_current_datacollectiongroup_attribute(
    Session: Callable, dcg_id: int, attr: str
):
    with Session() as session:
        query = session.query(DataCollectionGroup).filter(
            DataCollection.dataCollectionGroupId == dcg_id
        )
        first_result = query.first()
        return getattr(first_result, attr)


@pytest.fixture
def sqlalchemy_sessionmaker() -> sessionmaker:
    url = ispyb.sqlalchemy.url(CONST.SIM.DEV_ISPYB_DATABASE_CFG)
    engine = create_engine(url, connect_args={"use_pure": True})
    return sessionmaker(engine)


@pytest.fixture
def fetch_comment(sqlalchemy_sessionmaker) -> Callable:
    return partial(get_current_datacollection_comment, sqlalchemy_sessionmaker)


@pytest.fixture
def fetch_datacollection_attribute(sqlalchemy_sessionmaker) -> Callable:
    return partial(get_current_datacollection_attribute, sqlalchemy_sessionmaker)


@pytest.fixture
def fetch_datacollection_grid_attribute(sqlalchemy_sessionmaker) -> Callable:
    return partial(get_current_datacollection_grid_attribute, sqlalchemy_sessionmaker)


@pytest.fixture
def fetch_datacollection_position_attribute(sqlalchemy_sessionmaker) -> Callable:
    return partial(get_current_position_attribute, sqlalchemy_sessionmaker)


@pytest.fixture
def fetch_datacollectiongroup_attribute(sqlalchemy_sessionmaker) -> Callable:
    return partial(get_current_datacollectiongroup_attribute, sqlalchemy_sessionmaker)


@pytest.fixture
def dummy_params():
    dummy_params = ThreeDGridScan(
        **raw_params_from_file(
            "tests/test_data/parameter_json_files/test_gridscan_param_defaults.json"
        )
    )
    dummy_params.visit = "cm31105-5"
    return dummy_params


@pytest.fixture
def dummy_ispyb(dummy_params) -> StoreInIspyb:
    return StoreInIspyb(CONST.SIM.DEV_ISPYB_DATABASE_CFG)


@pytest.fixture
def dummy_ispyb_3d(dummy_params) -> StoreInIspyb:
    return StoreInIspyb(CONST.SIM.DEV_ISPYB_DATABASE_CFG)


@pytest.fixture
def zocalo_env():
    os.environ["ZOCALO_CONFIG"] = "/dls_sw/apps/zocalo/live/configuration.yaml"
