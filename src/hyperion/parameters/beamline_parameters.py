from typing import Any, Tuple, cast

from dodal.utils import get_beamline_name

from hyperion.log import LOGGER
from hyperion.parameters.constants import BEAMLINE_PARAMETER_PATHS

BEAMLINE_PARAMETER_KEYWORDS = ["FB", "FULL", "deadtime"]


class GDABeamlineParameters:
    params: dict[str, Any]

    def __repr__(self) -> str:
        return repr(self.params)

    def __getitem__(self, item: str):
        return self.params[item]

    @classmethod
    def from_lines(cls, file_name: str, config_lines: list[str]):
        ob = cls()
        config_lines_nocomments = [line.split("#", 1)[0] for line in config_lines]
        config_lines_sep_key_and_value = [
            # XXX removes all whitespace instead of just trim
            line.translate(str.maketrans("", "", " \n\t\r")).split("=")
            for line in config_lines_nocomments
        ]
        config_pairs: list[tuple[str, Any]] = [
            cast(Tuple[str, Any], param)
            for param in config_lines_sep_key_and_value
            if len(param) == 2
        ]
        for i, (param, value) in enumerate(config_pairs):
            try:
                # BEAMLINE_PARAMETER_KEYWORDS effectively raw string but whitespace removed
                if value not in BEAMLINE_PARAMETER_KEYWORDS:
                    config_pairs[i] = (
                        param,
                        cls.parse_value(value),
                    )
            except Exception as e:
                LOGGER.warning(f"Unable to parse {file_name} line {i}: {e}")

        ob.params = dict(config_pairs)
        return ob

    @classmethod
    def from_file(cls, path: str):
        with open(path) as f:
            config_lines = f.readlines()
        return cls.from_lines(path, config_lines)

    @classmethod
    def parse_value(cls, value: str):
        if value[0] == "[":
            return cls.parse_list(value[1:].strip())
        else:
            return cls.parse_list_element(value)

    @classmethod
    def parse_list_element(cls, value: str):
        if value == "Yes":
            return True
        elif value == "No":
            return False
        else:
            return float(value)

    @classmethod
    def parse_list(cls, value: str):
        list_output = []
        remaining = value.strip()
        i = 0
        while (i := remaining.find(",")) != -1:
            list_output.append(cls.parse_list_element(remaining[:i]))
            remaining = remaining[i + 1 :].lstrip()
        if (i := remaining.find("]")) != -1:
            list_output.append(cls.parse_list_element(remaining[:i]))
            remaining = remaining[i + 1 :].lstrip()
        else:
            raise ValueError("Missing closing ']' in list expression")
        return list_output


def get_beamline_parameters():
    beamline_name = get_beamline_name("s03")
    beamline_param_path = BEAMLINE_PARAMETER_PATHS.get(beamline_name)
    if beamline_param_path is None:
        raise KeyError(
            "No beamline parameter path found, maybe 'BEAMLINE' environment variable is not set!"
        )
    return GDABeamlineParameters.from_file(beamline_param_path)
