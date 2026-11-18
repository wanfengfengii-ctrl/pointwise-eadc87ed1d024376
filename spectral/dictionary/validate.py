from spectral.archive.codec import parse_rational, sequence
from spectral.dictionary.units import identities, validate_units
from spectral.dictionary.model import DictionaryRevision


def validate_dictionary(channels, components, channel_units, component_units, matrix):
    channels = identities(channels, "channels")
    components = identities(components, "components")
    if len(channels) > 24 or len(components) > 10:
        raise ValueError("dictionary exceeds supported dimensions")
    units = validate_units(channel_units, component_units, len(channels), len(components))
    matrix = tuple(tuple(parse_rational(value) for value in sequence(row, "matrix row")) for row in sequence(matrix, "matrix"))
    if len(matrix) != len(channels) or any(len(row) != len(components) for row in matrix):
        raise ValueError("matrix dimension mismatch")
    if any(value < 0 for row in matrix for value in row):
        raise ValueError("dictionary entries must be nonnegative")
    return DictionaryRevision("", "", None, channels, components, units, matrix)
