from uuid import uuid4
from spectral.dictionary.model import DictionaryRevision
from spectral.dictionary.units import UnitBindings
from spectral.dictionary.validate import validate_dictionary


def save_dictionary(catalog, channels, components, channel_units, component_units,
                    matrix, previous=None):
    value = validate_dictionary(channels, components, channel_units, component_units, matrix)
    revision_id = uuid4().hex
    with catalog.transaction():
        source_id = (get_dictionary_revision(catalog, previous).source_id
                     if previous is not None else revision_id)
        payload = value.payload()
        payload.update(source_id=source_id, previous=previous)
        catalog.append_record("dictionary", payload, revision_id)
        catalog.advance_head("dictionary", source_id, revision_id)
    return revision_id


def get_dictionary_revision(catalog, revision_id):
    data = catalog.read_record(revision_id, "dictionary")["data"]
    return DictionaryRevision(revision_id, data["source_id"], data["previous"],
                              tuple(data["channels"]), tuple(data["components"]),
                              UnitBindings(tuple(data["channel_units"]),
                                           tuple(data["component_units"])),
                              tuple(tuple(row) for row in data["matrix"]))
