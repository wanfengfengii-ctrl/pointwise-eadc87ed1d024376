from dataclasses import dataclass
from spectral.archive.codec import parse_rational, sequence
from spectral.archive.reading import read
from spectral.response.analysis import analyze_direction
from spectral.response.results import publish_direction_result


@dataclass(frozen=True)
class DirectionRequest:
    parent_id: str
    values: tuple


def direction(catalog, parent_id, values, fail_at=None):
    parent = read(catalog, parent_id)
    if parent["kind"] != "unmix":
        raise ValueError("direction requires an unmix parent")
    request = DirectionRequest(parent_id, tuple(parse_rational(value) for value in sequence(values, "direction")))
    if len(request.values) != len(parent["data"]["input"]["dictionary"]["channels"]):
        raise ValueError("direction dimension mismatch")
    responses = analyze_direction(parent["data"], request.values)
    return publish_direction_result(catalog, parent, request.values, responses, fail_at)
