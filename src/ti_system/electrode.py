from dataclasses import dataclass, field, InitVar
from typing import List

@dataclass
class Electrode:
    """Represents a single physical electrode with identifying attributes."""
    region: str
    name: str
    id: int

@dataclass
class ElectrodeGroup:
    """Represents a validated group of electrodes."""
    electrode_list: List[Electrode]
    target_voltage: float = 0.0
    expected_count: int = 2

    def __post_init__(self):
        """
        Performs validation after the object has been initialized by the dataclass.
        It now accesses expected_count as a regular instance property (self.expected_count).
        """
        if len(self.electrode_list) != self.expected_count:
            # Dynamic error message based on the expected count
            raise ValueError(
                f"ElectrodeGroup must consist of exactly {self.expected_count} Electrodes, "
                f"but {len(self.electrode_list)} were provided."
            )