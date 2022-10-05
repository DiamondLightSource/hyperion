from artemis.utils import Point2D

# def px_from_motor_position(offset:Point2D, pix_per_um_x:float, pix_per_um_y:float) -> Point2D:

# def motor_position_from_px(offset:Point2D, pix_per_um_x:float, pix_per_um_y:float)
# more complicated, need to know axes


def bottom_right_from_top_left(
    top_left: Point2D,
    steps_x: int,
    steps_y: int,
    step_size_x: float,
    step_size_y: float,
    pix_per_um_x: float,
    pix_per_um_y: float,
) -> Point2D:
    return Point2D(
        # step size is given in mm, pix in um
        int(steps_x * step_size_x * 1000 * pix_per_um_x + top_left.x),
        int(steps_y * step_size_y * 1000 * pix_per_um_y + top_left.y),
    )


#    def test_bottom_right_from_top_left(dummy_ispyb):
#
#  top_left = Point2D(123, 123)
# bottom_right = dummy_ispyb.bottom_right_from_top_left(
#        top_left, 20, 30, 0.1, 0.15, 0.37, 0.37
#   )
#  assert bottom_right.x == 863 and bottom_right.y == 1788
# bottom_right = dummy_ispyb.bottom_right_from_top_left(
#        top_left, 15, 20, 0.005, 0.007, 1, 1
#   )
#  assert bottom_right.x == 198 and bottom_right.y == 263
