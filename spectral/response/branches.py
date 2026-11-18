from dataclasses import dataclass
from fractions import Fraction

from spectral.dictionary.operators import DictionaryOperator
from spectral.unmixing.faces import enumerate_face_candidates, solve_face
from spectral.unmixing.linear import dot


@dataclass(frozen=True)
class ResponseBranch:
    constant: tuple
    slope: tuple
    residual_polynomial: tuple
    norm_polynomial: tuple
    right_limit: Fraction


def _square_polynomial(constant, slope):
    return (dot(constant, constant), 2 * dot(constant, slope), dot(slope, slope))


def _polynomial_value(polynomial, t):
    return sum((coefficient * t ** power
                for power, coefficient in enumerate(polynomial)), Fraction())


def enumerate_right_branches(matrix, values, direction):
    operator = DictionaryOperator(matrix)
    if len(direction) != operator.m:
        raise ValueError("direction dimension mismatch")
    for face in enumerate_face_candidates(matrix, values):
        constant = face.coefficients
        # A face is only reachable to the right of t = 0 when it stays inside
        # the non-negative orthant for some strictly positive interval.
        if any(x < 0 for x in constant):
            continue
        slope = solve_face(matrix, direction, face.support).coefficients
        # Zero components may enter (h >= 0), but cannot become negative.
        if any(x == 0 and h < 0 for x, h in zip(constant, slope)):
            continue
        # First positive time at which this branch leaves its face, capped at
        # one to preserve the frozen rational right-interval convention.
        limit = min([Fraction(1)] + [-x / h for x, h in
                    zip(constant, slope) if x > 0 and h < 0])
        residual = tuple(a - b for a, b in zip(face.reconstruction, values))
        residual_slope = tuple(a - b for a, b in
                               zip(operator.apply(slope), direction))
        yield ResponseBranch(constant, slope,
                             _square_polynomial(residual, residual_slope),
                             _square_polynomial(constant, slope), limit)


def _branch_key(branch, t):
    return (_polynomial_value(branch.residual_polynomial, t),
            _polynomial_value(branch.norm_polynomial, t))


def _lexicographic_difference(winner, branch):
    differences = tuple(b - w for b, w in
                        zip(branch.residual_polynomial,
                            winner.residual_polynomial))
    if not any(differences):
        differences = tuple(b - w for b, w in
                            zip(branch.norm_polynomial,
                                winner.norm_polynomial))
    first = next((i for i, value in enumerate(differences) if value), None)
    return differences, first


def _lexicographic_dominates(winner, branch, t):
    # The sign of the polynomial difference at a small positive t must be the
    # sign of its first non-zero coefficient.
    differences, first = _lexicographic_difference(winner, branch)
    if first is None:
        return True
    tail = sum((abs(differences[j]) * t ** (j - first)
                for j in range(first + 1, len(differences))), Fraction())
    return differences[first] > tail


def choose_right_branch(branches):
    branches = tuple(branches)
    if not branches:
        raise ValueError("no feasible right branch")
    # For sufficiently small positive t the lexicographic order of the
    # residual polynomial and then the coefficient-norm polynomial reproduces
    # the exact right derivative of the canonical mapping.
    winner = min(branches,
                 key=lambda b: (b.residual_polynomial, b.norm_polynomial))
    # Halve to a strictly positive rational point where every branch is still
    # feasible, the winner stays the minimizer and each lexicographic order is
    # already settled. Exact rational halving needs no polynomial roots.
    bound = winner.right_limit
    while True:
        trial = bound / 2
        feasible = all(x + trial * h >= 0
                       for branch in branches
                       for x, h in zip(branch.constant, branch.slope))
        winning = all(_branch_key(winner, trial) <= _branch_key(branch, trial)
                      for branch in branches)
        settled = all(_lexicographic_dominates(winner, branch, trial)
                      for branch in branches)
        if feasible and winning and settled:
            break
        bound = trial
    return ResponseBranch(winner.constant, winner.slope,
                          winner.residual_polynomial, winner.norm_polynomial, trial)
