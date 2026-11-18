from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations

from spectral.dictionary.operators import DictionaryOperator
from spectral.unmixing.linear import dot, minimum_norm_solution


@dataclass(frozen=True)
class FaceCandidate:
    support: tuple
    coefficients: tuple
    reconstruction: tuple
    residual_squared: Fraction
    norm_squared: Fraction


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
    # Solutions of the Gram normal equations are exactly the least-squares
    # minimizers on this face. Taking the minimum-norm solution keeps the face
    # admissible when its columns are linearly dependent (zero, repeated or
    # proportional columns); the canonical tie-break is completed globally by
    # solve_canonical over every face.
    local = minimum_norm_solution(gram, target, k)
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
            yield solve_face(operator.matrix, values, support)
