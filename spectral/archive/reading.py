def read(catalog, artifact_id):
    return catalog.read_artifact(artifact_id)


def read_parent_chain(catalog, artifact_id):
    artifacts = []
    records = []
    visited = set()

    def visit(reference):
        key = (reference["type"], reference["id"])
        if key in visited:
            return
        visited.add(key)
        if key[0] == "artifact":
            item = read(catalog, key[1])
            artifacts.append(item)
            for parent in item["parents"]:
                visit(parent)
            return
        item = catalog.read_record(key[1])
        records.append(item)
        data = item["data"]
        if item["kind"] == "cohort":
            visit({"type": "record", "id": data["dictionary"]["revision_id"]})
            for measurement in data["measurements"]:
                visit({"type": "record", "id": measurement["revision_id"]})
        elif item["kind"] in ("dictionary", "measurement"):
            if data.get("previous"):
                visit({"type": "record", "id": data["previous"]})
            if item["kind"] == "measurement":
                visit({"type": "record", "id": data["batch_id"]})
        elif item["kind"] == "batch":
            for revision_id in data["revision_ids"]:
                visit({"type": "record", "id": revision_id})

    visit({"type": "artifact", "id": artifact_id})
    return {"artifacts": artifacts, "records": records}
