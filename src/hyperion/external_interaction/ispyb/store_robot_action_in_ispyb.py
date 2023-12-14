import ispyb
from ispyb.connector.mysqlsp.main import ISPyBMySQLSPConnector as Connector
from ispyb.sp.mxacquisition import MXAcquisition

from hyperion.external_interaction.ispyb.ispyb_dataclass import (
    RobotLoadIspybParams,
)
from hyperion.external_interaction.ispyb.ispyb_utils import (
    get_current_time_string,
    get_session_id_from_visit,
    get_visit_string_from_path,
)
from hyperion.parameters.plan_specific.wait_for_robot_load_then_center_params import (
    WaitForRobotLoadThenCentreInternalParameters,
    WaitForRobotLoadThenCentreParams,
)


class StoreRobotLoadInIspyb:
    def __init__(
        self, ispyb_config, parameters: WaitForRobotLoadThenCentreInternalParameters
    ) -> None:
        self.ISPYB_CONFIG_PATH: str = ispyb_config
        self.experiment_params: WaitForRobotLoadThenCentreParams = (
            parameters.experiment_params
        )
        self.ispyb_params: RobotLoadIspybParams = (
            parameters.hyperion_params.ispyb_params
        )
        self.entry_id: int | None = None

    def _get_session_id(self, conn: Connector, visit_path: str):
        visit = get_visit_string_from_path(visit_path)
        if not visit:
            raise ValueError(f"Visit not found from {visit_path}")
        return get_session_id_from_visit(conn, visit)

    def _store_data(self, conn: Connector):
        mx_acquisition: MXAcquisition = conn.mx_acquisition
        session_id = self._get_session_id(conn, self.ispyb_params.visit_path)
        params = mx_acquisition.get_robot_action_params()

        params["session_id"] = session_id
        params["sample_id"] = self.ispyb_params.sample_id
        params["action_type"] = "LOAD"
        params["start_timestamp"] = self.experiment_params.robot_load_start_time
        params["container_location"] = self.experiment_params.sample_container_location
        params["dewar_location"] = self.experiment_params.sample_dewar_location
        params["sample_barcode"] = self.ispyb_params.sample_barcode

        return mx_acquisition.upsert_robot_action(list(params.values()))

    def begin_deposition(self):
        with ispyb.open(self.ISPYB_CONFIG_PATH) as conn:
            assert conn is not None, "Failed to connect to ISPyB"
            self.entry_id = self._store_data(conn)

    def end_deposition(self, success: str, reason: str):
        assert (
            self.entry_id is not None
        ), "Can't end robot load ISPyB entry as it was never started"
        with ispyb.open(self.ISPYB_CONFIG_PATH) as conn:
            assert conn is not None, "Failed to connect to ISPyB"
            mx_acquisition: MXAcquisition = conn.mx_acquisition
            params = mx_acquisition.get_robot_action_params()

            session_id = self._get_session_id(conn, self.ispyb_params.visit_path)

            params["id"] = self.entry_id
            params["session_id"] = session_id
            params["end_timestamp"] = get_current_time_string()
            params["status"] = success
            params["message"] = reason
            params["snapshot_after"] = ""
            params["snapshot_before"] = ""

            mx_acquisition.upsert_robot_action(list(params.values()))
