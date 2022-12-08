# import pytest
#
# artemis.parameters.parameters Point3D
# from artemis.external_interaction.zocalo_interaction import run_end, run_start, wait_for_result
#
# #This is dangerous until this is resolved, we can break prod zocalo with fake messages
# @pytest.mark.skip(
#     "Requires being able to change the zocalo env (https://github.com/DiamondLightSource/python-artemis/issues/356)"
# )
# @pytest.mark.s03
# def test_when_running_start_stop_then_get_expected_returned_results():
#     dcids = [1, 2]
#     for dcid in dcids:
#         run_start(dcid)
#     for dcid in dcids:
#         run_end(dcid)
#     assert wait_for_result(4) == Point3D(x=3.4, y=2.3, z=1.2)
#
