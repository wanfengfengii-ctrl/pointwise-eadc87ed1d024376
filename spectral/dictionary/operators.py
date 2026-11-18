from fractions import Fraction


class DictionaryOperator:
    def __init__(self, matrix):
        self.matrix = tuple(tuple(row) for row in matrix)
        if not self.matrix or not self.matrix[0]:
            raise ValueError("empty matrix")
        self.m = len(self.matrix)
        self.n = len(self.matrix[0])
        if any(len(row) != self.n for row in self.matrix):
            raise ValueError("ragged matrix")

    def apply(self, coefficients):
        if len(coefficients) != self.n:
            raise ValueError("coefficient dimension mismatch")
        return tuple(sum((a * x for a, x in zip(row, coefficients)), Fraction())
                     for row in self.matrix)

    def adjoint(self, values):
        if len(values) != self.m:
            raise ValueError("channel dimension mismatch")
        return tuple(sum((self.matrix[i][j] * values[i] for i in range(self.m)),
                         Fraction()) for j in range(self.n))

    def columns(self, positions):
        positions = tuple(positions)
        if len(set(positions)) != len(positions) or any(
                type(j) is not int or j < 0 or j >= self.n for j in positions):
            raise ValueError("invalid component positions")
        return tuple(tuple(row[j] for j in positions) for row in self.matrix)
