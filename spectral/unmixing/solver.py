from dataclasses import dataclass
from fractions import Fraction
from spectral.archive.codec import parse_rational, sequence
from spectral.dictionary.operators import DictionaryOperator
from spectral.unmixing.faces import enumerate_face_candidates


@dataclass(frozen=True)
class CanonicalSolution:
    coefficients: tuple
    reconstruction: tuple
    residual_squared: Fraction


def validated_problem(matrix, values):
    matrix = tuple(tuple(parse_rational(value) for value in sequence(row, "matrix row")) for row in sequence(matrix, "matrix"))
    operator = DictionaryOperator(matrix)
    values = tuple(parse_rational(value) for value in sequence(values, "measurement values"))
    if operator.m > 24 or operator.n > 10 or len(values) != operator.m:
        raise ValueError("unsupported problem dimensions")
    if any(value < 0 for row in matrix for value in row):
        raise ValueError("negative dictionary entry")
    return matrix, values


def solve_canonical(matrix, values):
    matrix, values = validated_problem(matrix, values)
    best = None
    for candidate in enumerate_face_candidates(matrix, values):
        if any(value < 0 for value in candidate.coefficients):
            continue
        key = (candidate.residual_squared, candidate.norm_squared)
        if best is None or key < best[0]:
            best = (key, candidate)
    candidate = best[1]
    return CanonicalSolution(candidate.coefficients, candidate.reconstruction,
                             candidate.residual_squared)
