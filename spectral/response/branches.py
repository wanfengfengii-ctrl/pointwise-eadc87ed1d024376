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


def enumerate_right_branches(matrix, values, direction):
    operator = DictionaryOperator(matrix)
    if len(direction) != operator.m:
        raise ValueError("direction dimension mismatch")
    candidates = [candidate for candidate in enumerate_face_candidates(matrix, values)
                  if all(x >= 0 for x in candidate.coefficients)]
    base = min(candidates, key=lambda c: (c.residual_squared, c.norm_squared))
    support = tuple(j for j, x in enumerate(base.coefficients) if x > 0)
    slope = solve_face(matrix, direction, support).coefficients
    limit = min([Fraction(1)] + [-x / h for x, h in
                zip(base.coefficients, slope) if x > 0 and h < 0])
    residual = tuple(a - b for a, b in zip(base.reconstruction, values))
    residual_slope = tuple(a - b for a, b in
                           zip(operator.apply(slope), direction))
    yield ResponseBranch(base.coefficients, slope,
                         _square_polynomial(residual, residual_slope),
                         _square_polynomial(base.coefficients, slope), limit)


def choose_right_branch(branches):
    branches = tuple(branches)
    if not branches:
        raise ValueError("no feasible right branch")
    return min(branches, key=lambda b: (b.residual_polynomial[0], b.norm_polynomial[0]))
