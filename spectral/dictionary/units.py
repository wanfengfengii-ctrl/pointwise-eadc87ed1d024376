from dataclasses import dataclass
from spectral.archive.codec import sequence


def identities(values, name):
    values = sequence(values, name)
    if (not values or any(not isinstance(x, str) or not x.strip() for x in values)
            or len(set(values)) != len(values)):
        raise ValueError("invalid or duplicate " + name)
    return values


@dataclass(frozen=True)
class UnitBindings:
    channels: tuple
    components: tuple


def validate_units(channel_units, component_units, channel_count, component_count):
    channel_units = sequence(channel_units, "channel units")
    component_units = sequence(component_units, "component units")
    if len(channel_units) != channel_count or len(component_units) != component_count:
        raise ValueError("unit dimension mismatch")
    if any(not isinstance(x, str) or not x.strip()
           for x in channel_units + component_units):
        raise ValueError("empty unit")
    return UnitBindings(channel_units, component_units)


def require_matching_units(actual, expected):
    if tuple(actual) != tuple(expected):
        raise ValueError("channel unit mismatch")
