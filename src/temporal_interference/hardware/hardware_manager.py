# hardware_manager.py (MODIFIED)
#
# This is the universal class handling all interaction with drivers and hardware.
# It functions as a Hardware Abstraction Layer (HAL).

import logging
import threading # Note: RLock is no longer used here
from typing import Dict, Any, Callable

# Local imports (assumed)
from .waveform_generator import (
    AbstractWaveformGenerator,
    OutputState,
    WaveformShape
)

logger = logging.getLogger(__name__)

class HardwareManager:
    """
    The universal class (HAL) for all interaction with waveform generator drivers.
    
    MODIFICATION: This class no longer implements a universal I/O lock.
    It relies on the underlying drivers to be individually thread-safe.
    This prevents I/O bottlenecks between independent instruments.
    """
    
    def __init__(self, drivers: Dict[str, AbstractWaveformGenerator]):
        """
        Initializes the HardwareManager.

        Args:
            drivers (Dict[str, AbstractWaveformGenerator]): A dictionary
                mapping a unique driver ID (e.g., "gen1") to its
                initialized driver instance.
        """
        self.drivers: Dict[str, AbstractWaveformGenerator] = drivers
        
        # MODIFICATION: The universal I/O lock has been removed.
        # self._io_lock = threading.RLock()
        
        # Mapping: logical_channel_id -> (driver_instance, physical_channel_num)
        self._channel_mapping: Dict[str, tuple[AbstractWaveformGenerator, int]] = {}
        
        logger.info(f"HardwareManager initialized with drivers: {list(drivers.keys())}")

    # --- NEW: Connection Status Property ---
    @property
    def is_connected(self) -> bool:
        """
        Checks if all managed drivers are currently connected.
        Returns False if no drivers are loaded.
        """
        if not self.drivers:
            logger.warning("HardwareManager.is_connected: No drivers are loaded.")
            return False
        
        # Return True only if all drivers report they are connected
        all_connected = all(driver.is_connected for driver in self.drivers.values())
        return all_connected

    def register_channel_mapping(self, 
                                 logical_channel_id: str, 
                                 driver_id: str, 
                                 physical_channel_num: int):
        """
        Maps a logical channel ID (used by TIChannel) to a specific
        driver and its physical channel number.
        """
        if driver_id not in self.drivers:
            msg = f"Driver ID '{driver_id}' not found in HardwareManager. Cannot map '{logical_channel_id}'."
            logger.error(msg)
            raise ValueError(msg)
            
        driver = self.drivers[driver_id]
        
        if logical_channel_id in self._channel_mapping:
            msg = f"Logical channel '{logical_channel_id}' is already mapped. Overwriting."
            logger.warning(msg)

        self._channel_mapping[logical_channel_id] = (driver, physical_channel_num)
        logger.info(f"Mapped logical channel '{logical_channel_id}' to driver '{driver_id}' (Phys Ch {physical_channel_num})")

    def _get_driver_and_channel(self, logical_channel_id: str) -> tuple[AbstractWaveformGenerator, int]:
        """
        Internal helper to resolve a logical channel ID to its
        driver instance and physical channel number.
        """
        try:
            return self._channel_mapping[logical_channel_id]
        except KeyError:
            logger.error(f"No mapping found for logical channel: {logical_channel_id}")
            raise LookupError(f"No driver/channel mapping found for logical channel ID: {logical_channel_id}")

    def _execute_io(self, 
                    logical_channel_id: str, 
                    io_func: Callable[[AbstractWaveformGenerator, int], Any], 
                    description: str) -> Any:
        """
        The core I/O execution method.
        
        It resolves the channel and executes the provided function.
        MODIFICATION: The universal lock has been removed. Thread-safety
        is now the responsibility of the driver.
        """
        driver, phys_ch = self._get_driver_and_channel(logical_channel_id)
        
        # MODIFICATION: Lock removed.
        # with self._io_lock:
        try:
            # The driver itself is responsible for thread-safe I/O.
            return io_func(driver, phys_ch)
        except Exception as e:
            # Catch, log, and re-raise exceptions to be handled by callers
            logger.error(f"Hardware I/O failed for '{logical_channel_id}' ({description}): {e}", exc_info=True)
            raise

    # --- NEW: Connection/Management Methods ---

    def connect_all(self):
        """
        Connects to all managed hardware drivers.
        MODIFICATION: This method now correctly checks the 'is_connected'
        property on the driver.
        """
        # This method is not internally locked, as connecting independent
        # devices can and should happen concurrently if the drivers support it.
        # The Keysight driver's lock is per-resource, so connecting two
        # *different* Keysight devices will be thread-safe and concurrent.
        logger.info("Connecting to all hardware drivers...")
        for driver_id, driver in self.drivers.items():
            try:
                # MODIFICATION: Use the 'is_connected' property
                if not driver.is_connected:
                    driver.connect()
                    logger.info(f"Successfully connected to '{driver_id}'.")
                else:
                    logger.info(f"Driver '{driver_id}' is already connected.")
            except Exception as e:
                logger.error(f"Failed to connect to '{driver_id}': {e}", exc_info=True)
                # Decide on error handling: re-raise to stop startup, or continue?
                # Re-raising is safer.
                raise
        logger.info("All hardware connections established.")

    def disconnect_all(self):
        """
        Disconnects from all managed hardware drivers.
        MODIFICATION: This method now correctly checks the 'is_connected'
        property on the driver.
        """
        logger.info("Disconnecting from all hardware drivers...")
        for driver_id, driver in self.drivers.items():
            try:
                # MODIFICATION: Use the 'is_connected' property
                if driver.is_connected:
                    driver.disconnect()
                    logger.info(f"Successfully disconnected from '{driver_id}'.")
            except Exception as e:
                # Log errors but continue disconnecting other devices
                logger.error(f"Error disconnecting from '{driver_id}': {e}", exc_info=True)
        logger.info("All hardware connections closed.")

    def enable_all_channels(self):
        """
        Enables the output for all *registered logical channels*.
        """
        logger.info(f"Enabling outputs for all {len(self._channel_mapping)} registered channels.")
        for driver in self.drivers.values():
            driver.enable_channels()
        logger.info("All registered channel outputs enabled.")

    def disable_all_channels(self):
        """
        Safely disables all *registered logical channels*.
        Sets amplitude to 0V and then sets output to OFF.
        This is a critical safety function.
        """
        logger.warning(f"Disabling outputs for all {len(self._channel_mapping)} registered channels (Safety Stop).")
        for driver in self.drivers.values():
            driver.disable_channels()
        for logical_channel_id in self._channel_mapping.keys():
            self.set_amplitude(logical_channel_id, 0.0)
        logger.warning("All registered channel outputs disabled.")

    def send_software_trigger(self):
        for driver in self.drivers.values():
            driver.send_software_trigger()
        logger.warning("All registered devices started signaling.")

    def abort(self):
        for driver in self.drivers.values():
            driver.abort()
        logger.warning("All registered devices stopped.")

    # --- Public I/O Interface (Setters) ---
    # These methods are now concurrent for independent devices.

    def set_output_state(self, logical_channel_id: str, state: OutputState):
        """Sets the output state for a logical channel."""
        self._execute_io(
            logical_channel_id,
            lambda d, c: d.set_output_state(c, state),
            f"set_output_state={state.value}"
        )

    def set_amplitude(self, logical_channel_id: str, voltage: float):
        """Sets the amplitude for a logical channel."""
        self._execute_io(
            logical_channel_id,
            lambda d, c: d.set_amplitude(c, voltage),
            f"set_amplitude={voltage:.4f}V"
        )

    def set_frequency(self, logical_channel_id: str, freq: float):
        """Sets the frequency for a logical channel."""
        self._execute_io(
            logical_channel_id,
            lambda d, c: d.set_frequency(c, freq),
            f"set_frequency={freq}Hz"
        )

    def set_offset(self, logical_channel_id: str, offset: float):
        """Sets the DC offset for a logical channel."""
        self._execute_io(
            logical_channel_id,
            lambda d, c: d.set_offset(c, offset),
            f"set_offset={offset:.4f}V"
        )

    def set_waveform_shape(self, logical_channel_id: str, shape: WaveformShape):
        """Sets the waveform shape for a logical channel."""
        self._execute_io(
            logical_channel_id,
            lambda d, c: d.set_waveform_shape(c, shape),
            f"set_waveform_shape={shape.value}"
        )

    # --- Public I/O Interface (Getters) ---

    def get_amplitude(self, logical_channel_id: str) -> float:
        """Gets the amplitude from a logical channel."""
        if self.is_connected:
            a = self._execute_io(
                logical_channel_id,
                lambda d, c: d.get_amplitude(c),
                "get_amplitude"
            )
            return a
        else:
            return 0.0
