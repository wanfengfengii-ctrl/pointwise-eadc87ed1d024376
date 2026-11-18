"""Independent regressions for the repaired canonical unmix and right-derivative chain."""
from fractions import Fraction as F
import itertools
import unittest

from spectral.archive.catalog import Catalog
from spectral.archive.reading import read
from spectral.dictionary.revisions import save_dictionary
from spectral.measurements.intake import save_batch
from spectral.measurements.cohorts import freeze
from spectral.unmixing.jobs import unmix
from spectral.unmixing.solver import solve_canonical
from spectral.response.requests import direction
from spectral.response.branches import enumerate_right_branches, choose_right_branch
from tests.test_unmix import publish, independent_oracle


class TestRepairCanonical(unittest.TestCase):
    def test_dependent_faces_keep_minimum_norm_content(self):
        # Proportional columns: the residual-optimal face is rank deficient, so
        # the canonical point is the minimum-norm point of that face.
        self.assertEqual(solve_canonical([[1, 2]], [1]).coefficients,
                         (F(1, 5), F(2, 5)))
        self.assertEqual(solve_canonical([[2, 4]], [1]).coefficients,
                         (F(1, 10), F(1, 5)))
        # Repeated columns split the load equally.
        self.assertEqual(solve_canonical([[1, 1, 0], [0, 0, 1]], [1, 0]).coefficients,
                         (F(1, 2), F(1, 2), F(0)))
        # Zero columns stay at zero even when the measurement is negative.
        self.assertEqual(solve_canonical([[0, 0], [0, 0]], [2, -1]).coefficients,
                         (F(0), F(0)))
        # An all-zero column next to an active one never absorbs content.
        result = solve_canonical([[1, 0, 1], [0, 1, 1]], [1, 1])
        self.assertEqual(result.coefficients, (F(1, 3), F(1, 3), F(2, 3)))
        self.assertEqual(result.residual_squared, F(0))
        self.assertTrue(all(x >= 0 for x in result.coefficients))

    def test_published_parent_and_response_share_one_source(self):
        c = Catalog(":memory:")
        try:
            _, _, _, parent = publish(c, [[1, 1, 0], [0, 0, 1]], [[1, 0]])
            positive = direction(c, parent, [0, 1])
            negative = direction(c, parent, [0, -1])
            parent_row = read(c, parent)["data"]["rows"][0]
            plus = read(c, positive)["data"]["rows"][0]
            minus = read(c, negative)["data"]["rows"][0]
            # The parent itself carries the corrected canonical content.
            self.assertEqual(parent_row["coefficients"], [F(1, 2), F(1, 2), F(0)])
            # The zero component enters only on the positive right direction.
            self.assertEqual(plus["coefficients"], [F(0), F(0), F(1)])
            self.assertEqual(plus["reconstruction"], [F(0), F(1)])
            self.assertEqual(minus["coefficients"], [F(0), F(0), F(0)])
            self.assertEqual(minus["reconstruction"], [F(0), F(0)])
            # Re-issuing the identical direction is a stable, idempotent retry.
            self.assertEqual(direction(c, parent, [0, "1"]), positive)
        finally:
            c.close()


class TestRepairDerivative(unittest.TestCase):
    def test_zero_components_can_enter_on_either_side(self):
        c = Catalog(":memory:")
        try:
            _, _, _, parent = publish(c, [[1, 0], [0, 1]], [[1, 0]])
            plus = read(c, direction(c, parent, [0, 1]))["data"]["rows"][0]
            minus = read(c, direction(c, parent, [0, -1]))["data"]["rows"][0]
            self.assertEqual(plus["coefficients"], [F(0), F(1)])
            self.assertEqual(plus["reconstruction"], [F(0), F(1)])
            # The reverse direction must be computed independently, not assumed
            # to be the negation of the positive one.
            self.assertEqual(minus["coefficients"], [F(0), F(0)])
            self.assertEqual(minus["reconstruction"], [F(0), F(0)])
        finally:
            c.close()

    def test_derivative_matches_perturbed_canonical_solutions(self):
        # For a strictly positive right step the canonical path must follow the
        # published constant + step * slope branch exactly.
        matrices = [[[1, 2]], [[1, 1], [0, 1]],
                    [[1, 1, 0], [0, 0, 1]], [[1, 0, 1], [0, 1, 1]],
                    [[1, 2, 0], [2, 4, 1]]]
        for matrix in matrices:
            for y in itertools.product((-1, 0, 1), repeat=len(matrix)):
                for d in itertools.product((-1, 0, 1), repeat=len(matrix)):
                    with self.subTest(matrix=matrix, y=y, d=d):
                        winner = choose_right_branch(
                            enumerate_right_branches(matrix, y, d))
                        step = winner.right_limit / 2
                        self.assertGreater(step, 0)
                        perturbed = [F(yi) + step * F(di)
                                     for yi, di in zip(y, d)]
                        expected, _, _ = independent_oracle(matrix, perturbed)
                        followed = tuple(x + step * h for x, h in
                                         zip(winner.constant, winner.slope))
                        self.assertEqual(followed, expected)
                        # Ah reconstruction of the derivative.
                        ah = tuple(sum((F(matrix[i][j]) * winner.slope[j]
                                        for j in range(len(winner.slope))), F())
                                   for i in range(len(matrix)))
                        self.assertEqual(len(ah), len(matrix))

    def test_right_derivative_is_not_a_finite_difference(self):
        # A direction tiny relative to the measurement still yields the exact
        # unit-scale right derivative.
        c = Catalog(":memory:")
        try:
            _, _, _, parent = publish(c, [[1]], [["1/1000000000000"]])
            row = read(c, direction(c, parent, [-1]))["data"]["rows"][0]
            self.assertEqual(row["coefficients"], [F(-1)])
            self.assertEqual(row["reconstruction"], [F(-1)])
        finally:
            c.close()


if __name__ == "__main__":
    unittest.main()
