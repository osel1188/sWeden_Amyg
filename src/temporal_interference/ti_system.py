from typing import List
from .electrode import ElectrodeGroup
from .waveform_generators.waveform_generator import AbstractWaveformGenerator

class TISystem:
    """Represents a single Temporal Interference (TI) channel composed of two electrode pairs."""
    def __init__(self, region: str, electrode_pairs: ElectrodeGroup):
        if len(electrode_pairs) != 2:
            raise ValueError("TISystem must be composed of exactly two ElectrodePairs.")
        self.region: str = region
        self.electrode_pairs: ElectrodeGroup = electrode_pairs

    def setup_target_voltage(self, voltage: float) -> None:
        """Sets the target voltage for a specific electrode pair."""
        self.electrode_pairs.target_voltage = voltage

    def setup_frequency(self, frequency: float) -> None:
        """Sets the operational frequency for this TI channel."""
        # Implementation depends on the hardware controller API.
        print(f"Setting frequency for region {self.region} to {frequency} Hz.")
