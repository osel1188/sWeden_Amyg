from typing import List
from .electrode import ElectrodePair

class TIChannel:
    """Represents a single Temporal Interference (TI) channel composed of two electrode pairs."""
    def __init__(self, region: str, electrode_pairs: List[ElectrodePair]):
        if len(electrode_pairs) != 2:
            raise ValueError("TIChannel must be composed of exactly two ElectrodePairs.")
        self.region: str = region
        self.electrode_pairs: List[ElectrodePair] = electrode_pairs

    def setup_target_voltage(self, pair_index: int, voltage: float) -> None:
        """Sets the target voltage for a specific electrode pair."""
        if 0 <= pair_index < len(self.electrode_pairs):
            self.electrode_pairs[pair_index].target_voltage = voltage
        else:
            raise IndexError("ElectrodePair index is out of range.")

    def setup_frequency(self, frequency: float) -> None:
        """Sets the operational frequency for this TI channel."""
        # Implementation depends on the hardware controller API.
        print(f"Setting frequency for region {self.region} to {frequency} Hz.")


