from dataclasses import dataclass
from uuid import uuid4
from spectral.measurements.validate import validate_measurement


@dataclass(frozen=True)
class MeasurementRevision:
    revision_id: str
    batch_id: str
    previous: object
    sample_id: str
    channels: tuple
    units: tuple
    values: tuple

    def payload(self):
        return {"batch_id": self.batch_id, "previous": self.previous,
                "sample_id": self.sample_id, "channels": self.channels,
                "units": self.units, "values": self.values}


def get_measurement_revision(catalog, revision_id):
    data = catalog.read_record(revision_id, "measurement")["data"]
    return MeasurementRevision(revision_id, data["batch_id"], data["previous"],
                               data["sample_id"], tuple(data["channels"]),
                               tuple(data["units"]), tuple(data["values"]))


def _store_measurement(catalog, batch_id, data, revision_id=None, previous=None):
    revision_id = revision_id or uuid4().hex
    payload = dict(data, batch_id=batch_id, previous=previous)
    catalog.append_record("measurement", payload, revision_id)
    source = batch_id + ":" + data["sample_id"]
    catalog.advance_head("measurement", source, revision_id)
    return revision_id


def append_measurement_revision(catalog, previous, values, channels=None, units=None):
    with catalog.transaction():
        old = get_measurement_revision(catalog, previous)
        catalog.read_record(old.batch_id, "batch")
        data = validate_measurement(old.sample_id,
                                    old.channels if channels is None else channels,
                                    old.units if units is None else units, values)
        return _store_measurement(catalog, old.batch_id, data, previous=previous)
