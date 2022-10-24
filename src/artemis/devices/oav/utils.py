from artemis.utils import Point2D


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
