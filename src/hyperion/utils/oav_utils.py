import bluesky.plan_stubs as bps
from dodal.devices.oav.oav_detector import OAV


def get_waveforms_to_image_scale(oav: OAV):
    """
    Returns the scale of the image.
    Args:
        oav (OAV): The OAV device in use.
    Returns:
        The (i_dimensions,j_dimensions) where n_dimensions is the scale of the camera image to the
        waveform values on the n axis.
    """
    image_size_i = yield from bps.rd(oav.cam.array_size.array_size_x)
    image_size_j = yield from bps.rd(oav.cam.array_size.array_size_y)
    waveform_size_i = yield from bps.rd(oav.mxsc.waveform_size_x)
    waveform_size_j = yield from bps.rd(oav.mxsc.waveform_size_y)
    return image_size_i / waveform_size_i, image_size_j / waveform_size_j
