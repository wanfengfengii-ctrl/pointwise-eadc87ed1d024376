from dataclasses import dataclass
from spectral.measurements.cohorts import get_cohort
from spectral.unmixing.solver import solve_canonical
from spectral.unmixing.accounting import build_unmix_payload
from spectral.archive.publication import publish_artifact


@dataclass(frozen=True)
class UnmixJob:
    cohort_id: str
    snapshot: dict


def unmix(catalog, cohort_id, fail_at=None):
    cohort = get_cohort(catalog, cohort_id)
    job = UnmixJob(cohort_id, cohort.snapshot)
    matrix = job.snapshot["dictionary"]["matrix"]
    solutions = [solve_canonical(matrix, row["values"])
                 for row in job.snapshot["measurements"]]
    payload = build_unmix_payload(job.cohort_id, job.snapshot, solutions)
    return publish_artifact(catalog, "unmix", "unmix:" + cohort_id, payload,
                            [{"type": "record", "id": cohort_id}], fail_at)
