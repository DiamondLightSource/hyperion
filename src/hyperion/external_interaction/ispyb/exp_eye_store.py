RobotActionID = int


def start_load(
    proposal_reference: str,
    visit_number: int,
    sample_id: int,
    dewar_location: int,
    container_location: int,
) -> RobotActionID:
    return 0


def end_load(action_id: RobotActionID, status: str, reason: str):
    pass
