from dataclasses import dataclass
from typing import Tuple

@dataclass
class Electrode:
    """Represents a single physical electrode with identifying attributes."""
    region: str
    name: str
    id: int

@dataclass(frozen=True) # Make immutable
class ElectrodePair:
    """
    Represents a validated group of exactly two electrodes
    that define a single logical channel.
    """
    electrodes: Tuple[Electrode, Electrode]

    def __len__(self) -> int:
        return len(self.electrodes)
