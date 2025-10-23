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

    def __str__(self) -> str:
        """Provides a human-readable string representation for display."""
        try:
            # Access electrodes directly
            e1 = self.electrodes[0]
            e2 = self.electrodes[1]
            # Format: (Region1/Name1) - (Region2/Name2)
            return f"({e1.region}/{e1.name}) - ({e2.region}/{e2.name})"
        except (AttributeError, IndexError, TypeError):
            # Fallback for empty or malformed pair
            return "Invalid Electrode Pair"