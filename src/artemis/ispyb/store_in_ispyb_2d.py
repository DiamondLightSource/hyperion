from src.artemis.ispyb.store_in_ispyb import StoreInIspyb


class StoreInIspyb2D(StoreInIspyb):
    def __init__(self, ispyb_config):
        super().__init__(ispyb_config)

    def _store_scan_data(self):
        data_collection_group_id = self._store_data_collection_group_table()

        data_collection_id = self._store_data_collection_table(data_collection_group_id)

        self._store_position_table(data_collection_id)

        grid_id = self._store_grid_info_table(data_collection_id)

        return [data_collection_id], [grid_id]
