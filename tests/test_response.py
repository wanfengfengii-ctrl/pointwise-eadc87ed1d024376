from fractions import Fraction as F
import itertools
import unittest

from spectral.archive.catalog import Catalog
from spectral.archive.reading import read
from spectral.response.requests import direction
from spectral.response.branches import enumerate_right_branches, choose_right_branch
from tests.test_unmix import publish, scenario, independent_oracle


class TestResponse(unittest.TestCase):
    def test_boundary_directions(self):
        c = Catalog(":memory:")
        try:
            _, _, _, parent = publish(c, [[1, 1, 0], [0, 0, 1]], [[1, 0]])
            positive = direction(c, parent, [0, 1])
            negative = direction(c, parent, [0, -1])
            actual_parent = read(c, parent)["data"]["rows"][0]["coefficients"]
            actual_positive = read(c, positive)["data"]["rows"][0]["coefficients"]
            actual_negative = read(c, negative)["data"]["rows"][0]["coefficients"]
            self.assertEqual(actual_parent, [F(1, 2), F(1, 2), F(0)])
            self.assertEqual(actual_positive, [F(0), F(0), F(1)])
            self.assertEqual(actual_negative, [F(0), F(0), F(0)])
            self.assertEqual(read(c, positive)["data"]["rows"][0]["reconstruction"], [F(0), F(1)])
            self.assertEqual(direction(c, parent, [0, "1.0"]), positive)
            scenario("V3.joint_handoff", {"A": [[1, 1, 0], [0, 0, 1]], "y": [1, 0], "d": [0, 1]},
                     [F(1, 2), F(1, 2), F(0)], actual_parent,
                     {"positive": [0, 0, 1], "negative": [0, 0, 0]},
                     {"positive": actual_positive, "negative": actual_negative},
                     ["spectral/unmixing/jobs.py", "spectral/unmixing/solver.py",
                      "spectral/response/analysis.py", "spectral/response/branches.py"],
                     "hand split of equal columns and max(0,y2) right derivatives")
        finally:
            c.close()

    def test_invalid_parent_and_direction(self):
        c = Catalog(":memory:")
        try:
            dictionary, _, _, parent = publish(c, [[1]], [[1]])
            count = c.counts()
            with self.assertRaises(KeyError):
                direction(c, "unknown", [1])
            with self.assertRaises(KeyError):
                direction(c, dictionary, [1])
            for values in ([], [1, 2], [None], [True], [0.1], ["1/0"], ["nan"]):
                with self.subTest(values=values), self.assertRaises(ValueError):
                    direction(c, parent, values)
            child = direction(c, parent, [1])
            with self.assertRaises(ValueError):
                direction(c, child, [1])
            self.assertEqual(c.counts()["artifacts"], count["artifacts"] + 1)
        finally:
            c.close()

    def test_right_interval_and_parent_binding(self):
        c = Catalog(":memory:")
        try:
            _, _, _, tiny = publish(c, [[1]], [["1/1000000"]])
            r = direction(c, tiny, [-1])
            self.assertEqual(read(c, r)["data"]["rows"][0]["coefficients"], [F(-1)])
            _, _, _, old = publish(c, [[1]], [[1]])
            _, _, _, new = publish(c, [[2]], [[1]])
            self.assertEqual(read(c, direction(c, old, [1]))["data"]["rows"][0]["coefficients"], [F(1)])
            self.assertEqual(read(c, direction(c, new, [1]))["data"]["rows"][0]["coefficients"], [F(1, 2)])
            _, _, _, batch = publish(c, [[1]], [[1], [-1], [0]], ["positive", "negative", "boundary"])
            rows = read(c, direction(c, batch, [1]))["data"]["rows"]
            self.assertEqual([r["sample_id"] for r in rows], ["positive", "negative", "boundary"])
            self.assertEqual([r["coefficients"] for r in rows], [[F(1)], [F(0)], [F(1)]])
        finally:
            c.close()

    def test_exact_right_intervals(self):
        # Independently account for every polynomial inequality over an interval,
        # rather than estimating a derivative with a finite step.
        matrices = [[[1, 2]], [[0, 0]], [[1, 1], [0, 1]],
                    [[1, 1, 0], [0, 0, 1]], [[1, 0, 1], [0, 1, 1]]]
        for a in matrices:
            for y in itertools.product((0, 1), repeat=len(a)):
                for d in itertools.product((-1, 1), repeat=len(a)):
                    branches = tuple(enumerate_right_branches(a, y, d))
                    winner = choose_right_branch(branches)
                    u, z, residual = independent_oracle(a, y)
                    self.assertEqual(winner.constant, u)
                    bound = winner.right_limit / 2
                    self.assertGreater(bound, 0)
                    for branch in branches:
                        for constant, slope in zip(branch.constant, branch.slope):
                            self.assertGreaterEqual(constant, 0)
                            self.assertGreaterEqual(constant + bound * slope, 0)
                        differences = tuple(b - w for b, w in zip(
                            branch.residual_polynomial, winner.residual_polynomial))
                        if not any(differences):
                            differences = tuple(b - w for b, w in zip(
                                branch.norm_polynomial, winner.norm_polynomial))
                        first = next((i for i, value in enumerate(differences) if value), None)
                        if first is not None:
                            self.assertGreater(differences[first], 0)
                            tail = sum(abs(differences[j]) * bound ** (j - first)
                                       for j in range(first + 1, len(differences)))
                            self.assertGreater(differences[first], tail)
                    for t in (bound, bound / 2):
                        perturbed = [F(yi) + t * di for yi, di in zip(y, d)]
                        exact, _, _ = independent_oracle(a, perturbed)
                        self.assertEqual(exact, tuple(x + t * h for x, h in
                                                      zip(winner.constant, winner.slope)))
                        self.assertEqual(tuple((x - b) / t for x, b in zip(exact, u)), winner.slope)
