"""Reproduce the published concentration and correction-response incident."""
from fractions import Fraction as F

from spectral.archive.catalog import Catalog
from spectral.archive.codec import encode_payload
from spectral.archive.reading import read
from spectral.dictionary.revisions import save_dictionary
from spectral.measurements.intake import save_batch
from spectral.measurements.cohorts import freeze
from spectral.unmixing.jobs import unmix
from spectral.response.requests import direction


def inspect_case(catalog, name, matrix, values, directions, expected_x, expected_h):
    channels = ["c" + str(i) for i in range(len(matrix))]
    components = ["k" + str(i) for i in range(len(matrix[0]))]
    dictionary = save_dictionary(catalog, channels, components,
                                 ["signal"] * len(channels),
                                 ["mg/L"] * len(components), matrix)
    batch = save_batch(catalog, channels, ["signal"] * len(channels),
                      [{"sample_id": name, "values": values}])
    revisions = catalog.read_record(batch, "batch")["data"]["revision_ids"]
    parent = unmix(catalog, freeze(catalog, dictionary, revisions))
    actual_x = read(catalog, parent)["data"]["rows"][0]["coefficients"]
    actual_h = []
    actual_ah = []
    for values_d in directions:
        child = direction(catalog, parent, values_d)
        row = read(catalog, child)["data"]["rows"][0]
        actual_h.append(row["coefficients"])
        actual_ah.append(row["reconstruction"])
    expected_ah = [[sum((F(a) * h for a, h in zip(row, derivative)), F())
                    for row in matrix] for derivative in expected_h]
    failed = (actual_x != expected_x or actual_h != expected_h
              or actual_ah != expected_ah)
    print(encode_payload({"case": name, "A": matrix, "y": values, "directions": directions,
                          "expected_x": expected_x, "actual_x": actual_x,
                          "expected_h": expected_h, "actual_h": actual_h,
                          "expected_Ah": expected_ah, "actual_Ah": actual_ah,
                          "matched": not failed}))
    return failed


def main():
    catalog = Catalog(":memory:")
    try:
        failed = [
            inspect_case(catalog, "joint", [[1, 1, 0], [0, 0, 1]], [1, 0],
                         [[0, 1], [0, -1]], [F(1, 2), F(1, 2), F(0)],
                         [[F(0), F(0), F(1)], [F(0), F(0), F(0)]]),
            inspect_case(catalog, "proportional", [[1, 2]], [1], [[1]],
                         [F(1, 5), F(2, 5)], [[F(1, 5), F(2, 5)]]),
            inspect_case(catalog, "boundary", [[1, 0], [0, 1]], [1, 0], [[0, 1]],
                         [F(1), F(0)], [[F(0), F(1)]])
        ]
    finally:
        catalog.close()
    print("UNMIX_RESPONSE_MISMATCH" if any(failed) else "UNMIX_RESPONSE_OK")
    return 1 if any(failed) else 0


if __name__ == "__main__":
    raise SystemExit(main())
