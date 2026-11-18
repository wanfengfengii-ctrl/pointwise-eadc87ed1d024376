from spectral.dictionary.operators import DictionaryOperator
from spectral.archive.publication import publish_artifact
from spectral.archive.codec import encode_payload


def build_response_payload(parent, direction, responses):
    data = parent["data"]
    dictionary = data["input"]["dictionary"]
    operator = DictionaryOperator(dictionary["matrix"])
    if len(responses) != len(data["rows"]):
        raise ValueError("incomplete direction results")
    rows = []
    for old, result in zip(data["rows"], responses):
        if result.sample_id != old["sample_id"]:
            raise ValueError("direction record identity mismatch")
        if operator.apply(result.coefficients) != result.reconstruction:
            raise ValueError("direction reconstruction mismatch")
        rows.append({"sample_id": result.sample_id,
                     "coefficients": result.coefficients,
                     "reconstruction": result.reconstruction})
    return {"parent_id": parent["id"], "cohort_id": data["cohort_id"],
            "channels": dictionary["channels"], "channel_units": dictionary["channel_units"],
            "components": dictionary["components"],
            "component_units": dictionary["component_units"],
            "direction": tuple(direction), "rows": rows}


def publish_direction_result(catalog, parent, direction, responses, fail_at=None):
    payload = build_response_payload(parent, direction, responses)
    key = "direction:" + parent["id"] + ":" + encode_payload(tuple(direction))
    return publish_artifact(catalog, "direction", key, payload,
                            [{"type": "artifact", "id": parent["id"]}], fail_at)
