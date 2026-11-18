from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations

from spectral.dictionary.operators import DictionaryOperator
from spectral.unmixing.linear import dot, solve_affine


@dataclass(frozen=True)
class FaceCandidate:
    support: tuple
    coefficients: tuple
    reconstruction: tuple
    residual_squared: Fraction
    norm_squared: Fraction


class _DependentFace(ValueError):
    pass


def solve_face(matrix, values, support):
    operator = DictionaryOperator(matrix)
    if len(values) != operator.m:
        raise ValueError("face observation dimension mismatch")
    support = tuple(support)
    selected = operator.columns(support)
    k = len(support)
    columns = [tuple(row[j] for row in selected) for j in range(k)]
    gram = [[dot(left, right) for right in columns] for left in columns]
    target = [dot(column, values) for column in columns]
    space = solve_affine(gram, target, k)
    if space.nullspace:
        raise _DependentFace("face has no unique coordinates")
    local = space.particular
    coefficients = [Fraction() for j in range(operator.n)]
    for position, value in zip(support, local):
        coefficients[position] = value
    reconstruction = operator.apply(coefficients)
    residual = tuple(a - b for a, b in zip(reconstruction, values))
    return FaceCandidate(support, tuple(coefficients), reconstruction,
                         dot(residual, residual), dot(coefficients, coefficients))


def enumerate_face_candidates(matrix, values):
    operator = DictionaryOperator(matrix)
    for size in range(operator.n + 1):
        for support in combinations(range(operator.n), size):
            try:
                candidate = solve_face(operator.matrix, values, support)
            except _DependentFace:
                continue
            yield candidate
