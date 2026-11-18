import itertools
import json
from fractions import Fraction as F
import unittest

from spectral.archive.catalog import Catalog
from spectral.archive.codec import encode_payload, decode_payload
from spectral.archive.reading import read
from spectral.dictionary.revisions import save_dictionary
from spectral.measurements.intake import save_batch
from spectral.measurements.cohorts import freeze
from spectral.unmixing.jobs import unmix
from spectral.unmixing.solver import solve_canonical


def publish(catalog, matrix, values, sample_ids=None):
    channels = ["c" + str(i) for i in range(len(matrix))]
    components = ["k" + str(i) for i in range(len(matrix[0]))]
    dictionary = save_dictionary(catalog, channels, components, ["signal"] * len(channels),
                                 ["mg/L"] * len(components), matrix)
    sample_ids = sample_ids or ["s" + str(i) for i in range(len(values))]
    batch = save_batch(catalog, channels, ["signal"] * len(channels),
                      [{"sample_id": sid, "values": y} for sid, y in zip(sample_ids, values)])
    revisions = catalog.read_record(batch, "batch")["data"]["revision_ids"]
    cohort = freeze(catalog, dictionary, revisions)
    parent = unmix(catalog, cohort)
    return dictionary, revisions, cohort, parent


def scenario(case_id, inputs, expected, actual, downstream_expected, downstream_actual, paths, oracle):
    print("POINTWISE_SCENARIO " + encode_payload({
        "case_id": case_id, "input": inputs, "expected": expected, "actual": actual,
        "downstream_expected": downstream_expected, "downstream_actual": downstream_actual,
        "code_paths": paths, "oracle": oracle}))


def det(matrix):
    if not matrix:
        return F(1)
    return sum(((-1) ** j * matrix[0][j]
                * det([row[:j] + row[j + 1:] for row in matrix[1:]])
                for j in range(len(matrix))), F())


def cramer(matrix, target):
    denominator = det(matrix)
    if not denominator:
        raise ValueError("dependent equations")
    return tuple(det([row[:j] + [target[i]] + row[j + 1:]
                      for i, row in enumerate(matrix)]) / denominator
                 for j in range(len(target)))


def inner(a, b):
    return sum((x * y for x, y in zip(a, b)), F())


def subsets(count):
    for size in range(count + 1):
        yield from itertools.combinations(range(count), size)


def independent_oracle(matrix, values):
    # First project onto the cone using linearly independent generators.
    # Then lift that unique projection with a minimum norm equality problem.
    a = [[F(x) for x in row] for row in matrix]
    y = tuple(F(x) for x in values)
    m, n = len(a), len(a[0])
    projections = []
    for support in subsets(n):
        columns = [tuple(a[i][j] for i in range(m)) for j in support]
        gram = [[inner(c, d) for d in columns] for c in columns]
        if not det(gram):
            continue
        x = cramer(gram, [inner(c, y) for c in columns])
        if any(t < 0 for t in x):
            continue
        z = tuple(sum((a[i][j] * t for j, t in zip(support, x)), F()) for i in range(m))
        projections.append((sum(((z[i] - y[i]) ** 2 for i in range(m)), F()), z))
    residual, z = min(projections)
    lifts = []
    for support in subsets(n):
        b = [[a[i][j] for j in support] for i in range(m)]
        chosen = []
        for i in range(m):
            trial = chosen + [i]
            if det([[inner(b[r], b[s]) for s in trial] for r in trial]):
                chosen = trial
        g = [[inner(b[r], b[s]) for s in chosen] for r in chosen]
        multipliers = cramer(g, [z[r] for r in chosen])
        local = tuple(sum((b[r][j] * t for r, t in zip(chosen, multipliers)), F())
                      for j in range(len(support)))
        if any(t < 0 for t in local):
            continue
        if any(inner(row, local) != target for row, target in zip(b, z)):
            continue
        full = tuple(local[support.index(j)] if j in support else F() for j in range(n))
        lifts.append((inner(full, full), full))
    return min(lifts)[1], z, residual


class TestUnmix(unittest.TestCase):
    def test_unique_solution(self):
        with self.subTest(case="identity"):
            c = Catalog(":memory:")
            try:
                _, _, _, p = publish(c, [[1, 0], [0, 1]], [[2, 3], [4, 1]], ["z", "a"])
                result = read(c, p)["data"]
                self.assertEqual([r["sample_id"] for r in result["rows"]], ["z", "a"])
                self.assertEqual([r["coefficients"] for r in result["rows"]], [[F(2), F(3)], [F(4), F(1)]])
                self.assertTrue(all(r["residual_squared"] == 0 for r in result["rows"]))
            finally:
                c.close()
        exact = solve_canonical([["1/3"]], ["1/7"])
        self.assertEqual(exact.coefficients, (F(3, 7),))
        self.assertEqual(exact.reconstruction, (F(1, 7),))
        self.assertEqual(exact.residual_squared, 0)
        self.assertEqual(decode_payload(encode_payload(exact.coefficients)), [F(3, 7)])
        constrained = solve_canonical([[1, 1], [0, 1]], [0, 1])
        self.assertEqual(constrained.coefficients, (F(0), F(1, 2)))
        self.assertEqual(constrained.reconstruction, (F(1, 2), F(1, 2)))
        self.assertEqual(constrained.residual_squared, F(1, 2))
        self.assertEqual(solve_canonical([[1]], [-2]).coefficients, (F(0),))
        self.assertEqual(solve_canonical([[1]], [1]).coefficients, (F(1),))
        scenario("V1.constrained_projection", {"A": [[1, 1], [0, 1]], "y": [0, 1]},
                 [F(0), F(1, 2)], list(constrained.coefficients),
                 {"Ax": [F(1, 2), F(1, 2)], "rss": F(1, 2)},
                 {"Ax": list(constrained.reconstruction), "rss": constrained.residual_squared},
                 ["spectral/unmixing/solver.py", "spectral/unmixing/faces.py",
                  "spectral/unmixing/accounting.py"], "hand minimization of (x1+x2)^2+(x2-1)^2")

    def test_rank_deficient_canonical(self):
        self.assertEqual(solve_canonical([[1, 2]], [1]).coefficients, (F(1, 5), F(2, 5)))
        self.assertEqual(solve_canonical([[2, 1]], [1]).coefficients, (F(2, 5), F(1, 5)))
        self.assertEqual(solve_canonical([[0, 0], [0, 0]], [2, -1]).coefficients, (F(0), F(0)))
        self.assertEqual(solve_canonical([[1, 0, 1]], [0]).coefficients, (F(0),) * 3)
        self.assertEqual(solve_canonical([[1, 1, 0], [0, 0, 1]], [1, 0]).coefficients,
                         (F(1, 2), F(1, 2), F(0)))

    def test_independent_faces(self):
        matrices = [
            [[1, 2]], [[0, 0]], [[1, 1], [0, 1]], [[1, 1, 0], [0, 0, 1]],
            [[1, 2, 0], [2, 4, 1]], [[1, 0, 1], [0, 1, 1]],
            [[0, 1, 0], [0, 0, 0]]]
        for a in matrices:
            for y in itertools.product((-1, 0, 1), repeat=len(a)):
                with self.subTest(a=a, y=y):
                    expected = independent_oracle(a, y)
                    result = solve_canonical(a, y)
                    self.assertEqual((result.coefficients, result.reconstruction, result.residual_squared), expected)
                    for permutation in (tuple(reversed(range(len(a[0])))),):
                        reordered = [[row[j] for j in permutation] for row in a]
                        permuted = solve_canonical(reordered, y)
                        self.assertEqual(permuted.coefficients, tuple(result.coefficients[j] for j in permutation))
