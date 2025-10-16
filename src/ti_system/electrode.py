from dataclasses import dataclass
from typing import List

@dataclass
class Electrode:
    """Represents a single physical electrode with identifying attributes."""
    region: str
    name: str
    id: int

@dataclass
class ElectrodePair:
    """Represents a pair of electrodes and their spatial relationship."""
    electrode_list: List[Electrode]
    target_voltage: float = 0.0

    def __init__(self, electrode_list, *, expected_electrodes: int = 2):
        if len(self.electrode_list) != expected_electrodes:
            raise ValueError("ElectrodePair must consist of exactly two Electrodes.")

    def __post_init__(self):
        if len(self.electrode_list) != 2:
            raise ValueError("ElectrodePair must consist of exactly two Electrodes.")
    