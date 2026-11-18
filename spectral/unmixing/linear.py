from dataclasses import dataclass
from fractions import Fraction


def dot(left, right):
    if len(left) != len(right):
        raise ValueError("dot dimension mismatch")
    return sum((a * b for a, b in zip(left, right)), Fraction())


@dataclass(frozen=True)
class AffineSolution:
    particular: tuple
    nullspace: tuple


def row_reduce(matrix, rhs, variable_count=None):
    if len(matrix) != len(rhs):
        raise ValueError("linear row mismatch")
    n = variable_count if variable_count is not None else (len(matrix[0]) if matrix else 0)
    if any(len(row) != n for row in matrix):
        raise ValueError("linear column mismatch")
    rows = [[Fraction(value) for value in row] + [Fraction(b)]
            for row, b in zip(matrix, rhs)]
    pivots = []
    cursor = 0
    for column in range(n):
        pivot = next((i for i in range(cursor, len(rows)) if rows[i][column]), None)
        if pivot is None:
            continue
        rows[cursor], rows[pivot] = rows[pivot], rows[cursor]
        divisor = rows[cursor][column]
        rows[cursor] = [value / divisor for value in rows[cursor]]
        for i in range(len(rows)):
            if i != cursor and rows[i][column]:
                multiple = rows[i][column]
                rows[i] = [a - multiple * b for a, b in zip(rows[i], rows[cursor])]
        pivots.append(column)
        cursor += 1
        if cursor == len(rows):
            break
    if any(all(value == 0 for value in row[:n]) and row[n] != 0 for row in rows):
        raise ValueError("inconsistent linear equations")
    return tuple(tuple(row) for row in rows), tuple(pivots)


def solve_affine(matrix, rhs, variable_count=None):
    n = variable_count if variable_count is not None else (len(matrix[0]) if matrix else 0)
    rows, pivots = row_reduce(matrix, rhs, n)
    particular = [Fraction() for j in range(n)]
    for i, pivot in enumerate(pivots):
        particular[pivot] = rows[i][n]
    nullspace = []
    for free in range(n):
        if free in pivots:
            continue
        vector = [Fraction() for j in range(n)]
        vector[free] = Fraction(1)
        for i, pivot in enumerate(pivots):
            vector[pivot] = -rows[i][free]
        nullspace.append(tuple(vector))
    return AffineSolution(tuple(particular), tuple(nullspace))


def minimum_norm_solution(matrix, rhs, variable_count=None):
    space = solve_affine(matrix, rhs, variable_count)
    if not space.nullspace:
        return space.particular
    gram = [[dot(left, right) for right in space.nullspace] for left in space.nullspace]
    target = [-dot(vector, space.particular) for vector in space.nullspace]
    coefficients = solve_affine(gram, target).particular
    return tuple(value + sum((coefficient * vector[j]
                              for coefficient, vector in zip(coefficients, space.nullspace)),
                             Fraction())
                 for j, value in enumerate(space.particular))
