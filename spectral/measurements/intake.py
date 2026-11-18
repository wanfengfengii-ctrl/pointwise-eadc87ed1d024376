from uuid import uuid4
from spectral.measurements.validate import validate_batch
from spectral.measurements.revisions import _store_measurement


def save_batch(catalog, channels, units, records):
    items = validate_batch(channels, units, records)
    batch_id = uuid4().hex
    revision_ids = [uuid4().hex for item in items]
    with catalog.transaction():
        catalog.append_record("batch", {"revision_ids": revision_ids,
                                       "sample_ids": [item["sample_id"] for item in items]},
                              batch_id)
        for item, revision_id in zip(items, revision_ids):
            _store_measurement(catalog, batch_id, item, revision_id)
    return batch_id
