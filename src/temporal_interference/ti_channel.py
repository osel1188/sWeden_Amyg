import logging
import threading
from typing import  Callable

# Local imports (assumed)
from .electrode import ElectrodePair
from .waveform_generators.waveform_generator import (
    AbstractWaveformGenerator,
    WaveformShape,
    OutputState
)

# This class now encapsulates its own hardware lock
# to protect I/O operations and internal state.
class TIChannel:
    """Manages the state and hardware interaction for a single TI channel."""

    def __init__(self,
                 channel_id: str,
                 wavegen_channel_id: int,
                 electrode_pair: ElectrodePair,
                 waveform_generator: AbstractWaveformGenerator,
                 region_name: str):

        if wavegen_channel_id not in [1, 2]:
            raise ValueError("Physical channel ID must be 1 or 2.")
        
        self.channel_id: str = channel_id
        self.wavegen_channel: int = wavegen_channel_id
        self.pair: ElectrodePair = electrode_pair
        self.generator: AbstractWaveformGenerator = waveform_generator
        self._region: str = region_name

        # --- Configuration State ---
        self.target_voltage: float = 0.0
        self.target_frequency: float = 0.0
        self.ramp_duration_s: float = 1.0

        # --- Runtime State ---
        # This is the single source of truth for this channel's voltage.
        self._current_voltage: float = 0.0
        
        # --- MODIFICATION: Granular Hardware Lock ---
        # This lock protects all hardware I/O and reads/writes
        # to self._current_voltage, ensuring atomic operations.
        self._hw_lock = threading.Lock()

    def setup_target_voltage(self, volt: float):
        """Sets the target voltage for this channel."""
        self.target_voltage = max(0.0, volt)

    def setup_frequency(self, freq: float):
        """Sets the target frequency for this channel."""
        self.target_frequency = freq

    def setup_ramp_duration(self, duration_s: float):
        """Sets the ramp duration for this channel."""
        self.ramp_duration_s = max(0.0, duration_s)

    def apply_config(self) -> None:
        """
        Applies non-voltage configuration to the hardware.
        Sets voltage to 0.0 before enabling output.
        Thread-safe.
        """
        with self._hw_lock:
            logging.debug(f"CH{self.wavegen_channel} ({self._region}): Applying config. Freq={self.target_frequency} Hz.")
            self.generator.set_waveform_shape(self.wavegen_channel, WaveformShape.SINE)
            self.generator.set_frequency(self.wavegen_channel, self.target_frequency)
            self.generator.set_offset(self.wavegen_channel, 0.0)
            
    def set_output_state(self, state: OutputState) -> None:
        """Sets the output state (ON/OFF) for this channel. Thread-safe."""
        with self._hw_lock:
            logging.debug(f"CH{self.wavegen_channel} ({self._region}): Setting output state to {state.name}.")
            self.generator.set_output_state(self.wavegen_channel, state)
    
    def _set_amplitude_unsafe(self, voltage: float) -> None:
        """
        Internal method to set hardware amplitude and update state.
        MUST be called from within a `with self._hw_lock:` block.
        """
        self.generator.set_amplitude(self.wavegen_channel, voltage)
        self._current_voltage = voltage

    def set_amplitude(self, voltage: float) -> None:
        """
        Sets the hardware amplitude and updates internal current_voltage state.
        This is the primary method for changing voltage during a ramp.
        Thread-safe.
        """
        with self._hw_lock:
            self._set_amplitude_unsafe(voltage)

    def get_current_voltage(self) -> float:
        """Gets the current voltage of the channel. Thread-safe."""
        with self._hw_lock:
            return self._current_voltage

    def immediate_stop(self) -> None:
        """
        Immediately sets amplitude to 0V, turns output OFF, and updates state.
        Thread-safe.
        """
        with self._hw_lock:
            logging.warning(f"CH{self.wavegen_channel} ({self._region}): Immediate stop.")
            self.generator.set_amplitude(self.wavegen_channel, 0.0)
            self.generator.set_output_state(self.wavegen_channel, OutputState.OFF)
            self._current_voltage = 0.0