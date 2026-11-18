from dataclasses import dataclass
from spectral.measurements.snapshots import capture_inputs


@dataclass(frozen=True)
class FrozenCohort:
    cohort_id: str
    snapshot: dict


def freeze(catalog, dictionary_id, measurement_ids):
    with catalog.transaction():
        snapshot = capture_inputs(catalog, dictionary_id, measurement_ids)
        return catalog.append_record("cohort", snapshot.payload())


def get_cohort(catalog, cohort_id):
    return FrozenCohort(cohort_id, catalog.read_record(cohort_id, "cohort")["data"])
