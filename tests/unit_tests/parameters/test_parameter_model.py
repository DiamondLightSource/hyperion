from hyperion.parameters.gridscan import ThreeDGridScan


def test_minimal_3d_gridscan_params():
    test_params = ThreeDGridScan(
        sample_id=123,
        x_start_um=0,
        y_start_um=0,
        z_start_um=0,
        parameter_model_version="5.0.0",  # type: ignore
        visit="cm12345",
        file_name="test_file_name",
        y2_start_um=2,
        z2_start_um=2,
        x_steps=5,
        y_steps=7,
        z_steps=9,
    )
    assert test_params.num_images == 5 * 7 + 5 * 9
