from dataclasses import dataclass
from spectral.dictionary.units import UnitBindings


@dataclass(frozen=True)
class DictionaryRevision:
    revision_id: str
    source_id: str
    previous: object
    channels: tuple
    components: tuple
    units: UnitBindings
    matrix: tuple

    @property
    def channel_count(self):
        return len(self.channels)

    @property
    def component_count(self):
        return len(self.components)

    def payload(self):
        return {"source_id": self.source_id, "previous": self.previous,
                "channels": self.channels, "components": self.components,
                "channel_units": self.units.channels,
                "component_units": self.units.components, "matrix": self.matrix}
