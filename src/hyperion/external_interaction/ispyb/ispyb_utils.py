from __future__ import annotations

import datetime
import os
import re
from typing import Optional

from dodal.devices.detector import DetectorParams
from ispyb import NoResult
from ispyb.connector.mysqlsp.main import ISPyBMySQLSPConnector as Connector
from ispyb.sp.core import Core

from hyperion.external_interaction.ispyb.ispyb_dataclass import IspybParams
from hyperion.log import ISPYB_LOGGER
from hyperion.parameters.constants import CONST

VISIT_PATH_REGEX = r".+/([a-zA-Z]{2}\d{4,5}-\d{1,3})(/?$)"


def get_current_time_string():
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")


def get_ispyb_config():
    return os.environ.get("ISPYB_CONFIG_PATH", CONST.SIM.ISPYB_CONFIG)


def get_visit_string_from_path(path: Optional[str]) -> str | None:
    match = re.search(VISIT_PATH_REGEX, path) if path else None
    return str(match.group(1)) if match else None


def get_session_id_from_visit(conn: Connector, visit: str):
    try:
        core: Core = conn.core
        return core.retrieve_visit_id(visit)
    except NoResult:
        raise NoResult(f"No session ID found in ispyb for visit {visit}")


def get_visit_string(ispyb_params: IspybParams, detector_params: DetectorParams) -> str:
    assert ispyb_params and detector_params, "StoreInISPyB didn't acquire params"
    visit_path_match = get_visit_string_from_path(ispyb_params.visit_path)
    if visit_path_match:
        return visit_path_match
    visit_path_match = get_visit_string_from_path(detector_params.directory)
    if not visit_path_match:
        raise ValueError(
            f"Visit not found from {ispyb_params.visit_path} or {detector_params.directory}"
        )
    return visit_path_match


def get_xtal_snapshots(ispyb_params):
    if ispyb_params.xtal_snapshots_omega_start:
        xtal_snapshots = ispyb_params.xtal_snapshots_omega_start[:3]
        ISPYB_LOGGER.info(
            f"Using rotation scan snapshots {xtal_snapshots} for ISPyB deposition"
        )
    else:
        ISPYB_LOGGER.warning("No xtal snapshot paths sent to ISPyB!")
        xtal_snapshots = []
    return xtal_snapshots + [None] * (3 - len(xtal_snapshots))
