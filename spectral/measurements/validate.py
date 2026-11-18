from spectral.archive.codec import parse_rational, sequence
from spectral.dictionary.units import identities, require_matching_units


def validate_measurement(sample_id, channels, units, values):
    if not isinstance(sample_id, str) or not sample_id.strip():
        raise ValueError("empty sample identity")
    channels = identities(channels, "measurement channels")
    units = sequence(units, "measurement units")
    values = tuple(parse_rational(value) for value in sequence(values, "measurement values"))
    if not 1 <= len(channels) <= 24 or len(units) != len(channels) or len(values) != len(channels):
        raise ValueError("measurement dimension mismatch")
    if any(not isinstance(unit, str) or not unit.strip() for unit in units):
        raise ValueError("empty measurement unit")
    return {"sample_id": sample_id, "channels": channels, "units": units, "values": values}


def validate_batch(channels, units, records):
    records = sequence(records, "batch records")
    if not records:
        raise ValueError("empty batch")
    result = []
    seen = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != {"sample_id", "values"}:
            raise ValueError("record requires sample_id and values")
        item = validate_measurement(record["sample_id"], channels, units, record["values"])
        if item["sample_id"] in seen:
            raise ValueError("duplicate sample in batch")
        seen.add(item["sample_id"])
        result.append(item)
    return tuple(result)


def validate_measurement_binding(measurement, dictionary):
    if tuple(measurement.channels) != dictionary.channels:
        raise ValueError("channel identity or order mismatch")
    require_matching_units(measurement.units, dictionary.units.channels)
    if len(measurement.values) != dictionary.channel_count:
        raise ValueError("measurement dimension mismatch")
