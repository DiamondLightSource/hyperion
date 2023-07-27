import copy
import json
import os
import time
from os.path import join

from jinja2 import Environment, FileSystemLoader

from artemis.external_interaction.ispyb.ispyb_dataclass import IspybParams

ECR_to_copy = "template_ecr.xml"
other_parameter_file = "exp_params.json"

this_file_dir = os.path.dirname(os.path.abspath(__file__))


def create_new_ECRs(positions, ispyb_params: IspybParams):
    out_folder = ispyb_params.visit_path + "/xml"

    with open(join(this_file_dir, other_parameter_file)) as f:
        other_params = json.load(f)
        sample_template = {
            "sample_name": ispyb_params.sample_name,
            "visit_folder": ispyb_params.visit_path,
            "sample_container": ispyb_params.sample_container,
            "sample_location": ispyb_params.sample_location,
            "sample_id": ispyb_params.sample_id,
            "transmission": other_params["transmission"],
            "exposure_time": other_params["exposure_time"],
        }
        samples = {"samples": []}

    for pos in positions[1:]:
        new_sample = copy.deepcopy(sample_template)
        new_sample["x"] = pos[0] * 1000
        new_sample["y"] = pos[1] * 1000
        new_sample["z"] = pos[2] * 1000
        samples["samples"].append(new_sample)

    print(f"Using samples: {samples}")

    environment = Environment(loader=FileSystemLoader(this_file_dir))
    template = environment.get_template("template_ecr.xml")

    with open(
        join(out_folder, f"{ispyb_params.sample_name}_multipin_{time.time()}.xml"),
        mode="w",
        encoding="utf-8",
    ) as results:
        results.write(template.render(samples))


if __name__ == "__main__":
    positions = [(1, 2, 3), (2, 3, 4)]
    # create_new_ECRs("sample_1", positions, Magic".")
