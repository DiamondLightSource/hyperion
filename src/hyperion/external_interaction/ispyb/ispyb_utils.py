from __future__ import annotations

import datetime
import os

from ispyb import NoResult
from ispyb.connector.mysqlsp.main import ISPyBMySQLSPConnector as Connector
from ispyb.sp.core import Core

from hyperion.parameters.constants import CONST

VISIT_PATH_REGEX = r".+/([a-zA-Z]{2}\d{4,5}-\d{1,3})(/?$)"


def get_ispyb_config():
    return os.environ.get("ISPYB_CONFIG_PATH", CONST.SIM.ISPYB_CONFIG)


def get_session_id_from_visit(conn: Connector, visit: str):
    try:
        core: Core = conn.core
        return core.retrieve_visit_id(visit)
    except NoResult:
        raise NoResult(f"No session ID found in ispyb for visit {visit}")


def get_current_time_string():
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d %H:%M:%S")
