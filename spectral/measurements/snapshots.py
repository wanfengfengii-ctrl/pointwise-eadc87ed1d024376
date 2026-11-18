from dataclasses import dataclass
from spectral.archive.codec import sequence
from spectral.dictionary.revisions import get_dictionary_revision
from spectral.measurements.revisions import get_measurement_revision
from spectral.measurements.validate import validate_measurement_binding


@dataclass(frozen=True)
class FrozenInput:
    dictionary: object
    measurements: tuple

    def payload(self):
        dictionary = self.dictionary.payload()
        dictionary["revision_id"] = self.dictionary.revision_id
        measurements = []
        for item in self.measurements:
            value = item.payload()
            value["revision_id"] = item.revision_id
            measurements.append(value)
        return {"dictionary": dictionary, "measurements": measurements}


def capture_inputs(catalog, dictionary_id, measurement_ids):
    dictionary = get_dictionary_revision(catalog, dictionary_id)
    measurement_ids = sequence(measurement_ids, "measurement selection")
    if not measurement_ids or len(set(measurement_ids)) != len(measurement_ids):
        raise ValueError("empty or duplicate measurement selection")
    measurements = tuple(get_measurement_revision(catalog, item) for item in measurement_ids)
    identities = [(item.batch_id, item.sample_id) for item in measurements]
    if len(set(identities)) != len(identities):
        raise ValueError("multiple revisions of one sample in a cohort")
    for item in measurements:
        validate_measurement_binding(item, dictionary)
    return FrozenInput(dictionary, measurements)
