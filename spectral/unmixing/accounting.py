from spectral.dictionary.operators import DictionaryOperator
from spectral.unmixing.linear import dot


def check_unmix_accounting(matrix, values, row):
    operator = DictionaryOperator(matrix)
    if any(value < 0 for value in row["coefficients"]):
        raise ValueError("negative published coefficient")
    reconstruction = operator.apply(row["coefficients"])
    residual = tuple(a - b for a, b in zip(reconstruction, values))
    if (tuple(row["reconstruction"]) != reconstruction
            or row["residual_squared"] != dot(residual, residual)):
        raise ValueError("unmix accounting mismatch")


def build_unmix_payload(cohort_id, snapshot, solutions):
    if len(solutions) != len(snapshot["measurements"]):
        raise ValueError("incomplete unmix results")
    matrix = snapshot["dictionary"]["matrix"]
    rows = []
    for measurement, solution in zip(snapshot["measurements"], solutions):
        row = {"sample_id": measurement["sample_id"],
               "measurement_revision": measurement["revision_id"],
               "coefficients": solution.coefficients,
               "reconstruction": solution.reconstruction,
               "residual_squared": solution.residual_squared}
        check_unmix_accounting(matrix, measurement["values"], row)
        rows.append(row)
    return {"cohort_id": cohort_id, "input": snapshot, "rows": rows}
