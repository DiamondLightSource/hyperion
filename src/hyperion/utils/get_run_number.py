import os
import re
from typing import List

import hyperion.log


def _find_next_run_number_from_files(file_names: List[str]) -> int:
    valid_numbers = []

    for file_name in file_names:
        file_name = file_name.strip(".nxs")
        # Give warning if nexus file name isn't in expcted format, xxx_number.nxs
        match = re.search(r"_\d+$", file_name)
        if match is not None:
            valid_numbers.append(int(re.findall(r"\d+", file_name)[-1]))
        else:
            hyperion.log.LOGGER.warning(
                f"Identified nexus file {file_name} with unexpected format"
            )
        if len(valid_numbers) != 0:
            return max(valid_numbers) + 1
        else:
            return 1


def get_run_number(directory: str) -> int:
    nexus_file_names = [file for file in os.listdir(directory) if file.endswith(".nxs")]

    if len(nexus_file_names) == 0:
        return 1
    else:
        return _find_next_run_number_from_files(nexus_file_names)
