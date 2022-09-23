from dataclasses import dataclass

from dataclasses_json import dataclass_json


@dataclass
@dataclass_json
class TopupParameters:
    instability_time: float
    threshold_percentage: float
    total_exposure_time: float
