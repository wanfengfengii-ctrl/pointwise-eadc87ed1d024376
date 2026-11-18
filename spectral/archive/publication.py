from uuid import uuid4
from spectral.archive.codec import encode_payload


def publish_artifact(catalog, kind, logical_key, payload, parents, fail_at=None):
    if fail_at not in (None, "after_payload", "after_index"):
        raise ValueError("unknown publication failure stage")
    with catalog.transaction():
        for parent in parents:
            if parent["type"] == "record":
                catalog.read_record(parent["id"])
            elif parent["type"] == "artifact":
                catalog.read_artifact(parent["id"])
            else:
                raise ValueError("invalid parent type")
        existing = catalog.find_publication(logical_key)
        if existing is not None:
            saved = catalog.read_artifact(existing)
            if (saved["kind"] != kind or saved["parents"] != parents
                    or encode_payload(saved["data"]) != encode_payload(payload)):
                raise ValueError("logical publication conflict")
            return existing
        artifact_id = uuid4().hex
        catalog.stage_payload(artifact_id, payload)
        if fail_at == "after_payload":
            raise RuntimeError("publication failed after payload")
        catalog.stage_index(artifact_id, kind, logical_key, parents)
        if fail_at == "after_index":
            raise RuntimeError("publication failed after index")
        return artifact_id
