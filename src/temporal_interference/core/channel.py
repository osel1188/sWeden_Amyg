# channel.py (MODIFIED)

import logging
import threading
from typing import Callable

# Local imports (assumed)
from .electrode import ElectrodePair
# --- NEW IMPORT ---
from ..hardware.hardware_manager import HardwareManager
from ..hardware.waveform_generator import (
    WaveformShape,
    OutputState
)

# --- Define the module-level logger ---
logger = logging.getLogger(__name__)

class TIChannel:
    """
    Manages the *state* and *configuration* for a single TI channel.
    All hardware I/O is delegated to the HardwareManager.
    """

    def __init__(self,
                 channel_id: str,
                 wavegen_channel_id: int,
                 electrode_pair: ElectrodePair,
                 driver_id: str,
                 hw_manager: HardwareManager,
                 region_name: str):

        if wavegen_channel_id not in [1, 2]:
            raise ValueError("Physical channel ID must be 1 or 2.")
        
        self.channel_id: str = channel_id
        self.wavegen_channel: int = wavegen_channel_id
        self.pair: ElectrodePair = electrode_pair
        self._region: str = region_name
        
        # --- NEW: Store the driver ID for monitoring ---
        self.driver_id: str = driver_id 

        # --- NEW: Reference to the HAL ---
        self.hw_manager: HardwareManager = hw_manager

        # --- Register this logical channel with the HAL ---
        self.hw_manager.register_channel_mapping(
            self.channel_id,
            self.driver_id,
            self.wavegen_channel
        )

        # --- Configuration State (Unchanged) ---
        self.target_voltage: float = 0.0
        self.target_frequency: float = 0.0
        self.ramp_duration_s: float = 1.0

        # --- Runtime State ---
        # This is the single source of truth for this channel's *cached* state.
        self._current_voltage: float = 0.0
        
        # This lock *only* protects self._current_voltage.
        # All hardware I/O is protected by the manager's global lock.
        self._state_lock = threading.RLock()

    # --- setup_* methods are unchanged ---

    def setup_target_voltage(self, volt: float):
        """Sets the target voltage for this channel."""
        self.target_voltage = max(0.0, volt)

    def set_frequency(self, freq: float):
        """Sets the target frequency for this channel."""
        self.target_frequency = freq
        logger.debug(f"CH{self.wavegen_channel} ({self._region}): Applying config. Freq={self.target_frequency} Hz.")
        self.hw_manager.set_waveform_shape(self.channel_id, WaveformShape.SINE)
        self.hw_manager.set_frequency(self.channel_id, self.target_frequency)

    def set_ramp_duration(self, duration_s: float):
        """Sets the ramp duration for this channel."""
        self.ramp_duration_s = max(0.0, duration_s)

    # --- I/O Methods (MODIFIED) ---
            
    def set_output_state(self, state: OutputState) -> None:
        """Sets the output state (ON/OFF) via the manager."""
        # --- MODIFIED: Delegate to manager ---
        logger.debug(f"CH{self.wavegen_channel} ({self._region}): Setting output state to {state.name}.")
        self.hw_manager.set_output_state(self.channel_id, state)
    
    # --- REMOVED _set_amplitude_unsafe ---

    def set_amplitude(self, voltage: float) -> None:
        """
        Sets the hardware amplitude (via manager) and updates
        internal cached state.
        Thread-safe.
        """
        # --- MODIFIED: Delegate to manager AND update local state ---
        self.hw_manager.set_amplitude(self.channel_id, voltage)
        with self._state_lock:
            self._current_voltage = voltage

    def get_amplitude(self) -> None:
        """
        Get the hardware amplitude (via manager)
        """
        return self.hw_manager.get_amplitude(self.channel_id)

    def get_current_voltage(self) -> float:
        """
        Gets the *cached* current voltage of the channel.
        This is fast and does not perform I/O.
        Thread-safe.
        """
        # --- MODIFIED: Just returns cached state, but thread-safe ---
        with self._state_lock:
            return self._current_voltage

    def immediate_stop(self) -> None:
        """
        Immediately sets amplitude to 0V and turns output OFF via manager.
        Thread-safe.
        """
        # --- MODIFIED: Delegate to manager AND update local state ---
        with self._state_lock:
            logger.warning(f"CH{self.wavegen_channel} ({self._region}): Immediate stop.")
            # Set amplitude to 0 first
            self.hw_manager.set_amplitude(self.channel_id, 0.0)
            # Then turn off output
            self.hw_manager.set_output_state(self.channel_id, OutputState.OFF)
            self._current_voltage = 0.0