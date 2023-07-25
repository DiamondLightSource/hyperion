import copy
import time
import xml.etree.ElementTree as ET
from os.path import join

from artemis.log import LOGGER

ECR_to_copy = "exptTableParams.xml"


def create_new_ECRs(positions, ECR_folder):
    ECR_path = join(ECR_folder, ECR_to_copy)

    tree = ET.parse(ECR_path)
    root = tree.getroot()

    original_ecr = tree.find("extendedCollectRequest")
    root.remove(original_ecr)

    sample_position_template = (
        """<samplePosition><x>{0}</x><y>{1}</y><z>{2}</z></samplePosition>"""
    )

    sample_name = original_ecr.find("sampleName").text

    for position in positions:
        new_ecr = copy.deepcopy(original_ecr)

        sample_pos = ET.fromstring(sample_position_template.format(*position))
        new_ecr.find("centringMode").text = "DISABLE"
        new_ecr.append(sample_pos)
        root.append(new_ecr)

    ET.indent(root)

    out_file_path = join(ECR_folder, f"{sample_name}_full_multipin_{time.time()}.xml")
    LOGGER.info(
        f"Creating XML in {out_file_path}: {ET.tostring(root, encoding='unicode')}"
    )

    tree.write(out_file_path)


if __name__ == "__main__":
    positions = [(1, 2, 3), (2, 3, 4)]
    create_new_ECRs(positions, "/tmp/gda/i03/data/2023/cm33866-3/xml")
