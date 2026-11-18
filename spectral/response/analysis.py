from dataclasses import dataclass
from spectral.dictionary.operators import DictionaryOperator
from spectral.response.branches import enumerate_right_branches, choose_right_branch


@dataclass(frozen=True)
class DirectionResponse:
    sample_id: str
    coefficients: tuple
    reconstruction: tuple


def analyze_direction(parent_payload, direction):
    snapshot = parent_payload["input"]
    operator = DictionaryOperator(snapshot["dictionary"]["matrix"])
    if len(parent_payload["rows"]) != len(snapshot["measurements"]):
        raise ValueError("incomplete parent rows")
    responses = []
    for measurement, saved in zip(snapshot["measurements"], parent_payload["rows"]):
        if (saved["sample_id"] != measurement["sample_id"]
                or saved["measurement_revision"] != measurement["revision_id"]):
            raise ValueError("parent record identity mismatch")
        branch = choose_right_branch(enumerate_right_branches(
            operator.matrix, measurement["values"], direction))
        if branch.constant != tuple(saved["coefficients"]):
            raise ValueError("parent and response canonical mapping disagree")
        responses.append(DirectionResponse(measurement["sample_id"], branch.slope,
                                           operator.apply(branch.slope)))
    return tuple(responses)
