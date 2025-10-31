# --- Conditional VISA Import ---
from .mockup_config import USE_MOCK

if USE_MOCK:
    # Use the local mock_visa module
    from . import mock_visa as visa
else:
    # Use the real, installed pyvisa library
    try:
        import pyvisa as visa
    except ImportError:
        # Handle case where pyvisa is not installed in live mode
        logging.critical("pyvisa is not installed. Run 'pip install pyvisa'")
        raise

import time
import logging
# RLock is correct, as it's used for re-entrant I/O calls
import threading
from typing import Optional, Any, Dict, List, cast

from .waveform_generator import (
    AbstractWaveformGenerator,
    OutputState,
    WaveformShape,
    TriggerSource
)

# Setup a standard logger.
logger = logging.getLogger(__name__)

class KeysightEDU33212A(AbstractWaveformGenerator, model_id="KeysightEDU33212A"):
    """
    A concrete implementation for a Keysight EDU33220A series waveform generator.
    
    MODIFICATION: This driver is now internally thread-safe. It uses its
    class-level, per-resource RLock to protect all I/O operations (_write, _query),
    in addition to connection management.
    
    MODIFICATION: This driver now maintains an internal 'shadow state' of
    all parameters pushed to the device, allowing for logical 'get' methods
    that do not perform I/O.
    """
    
    # --- Class-level shared resource management ---
    _rm = visa.ResourceManager()
    _active_connections: Dict[str, Dict[str, Any]] = {}
    # RLock is used to prevent deadlock and protect shared resources
    _resource_lock = threading.RLock()
    # ----------------------------------------------

    def __init__(
        self,
        resource_id: str,
        name: str = "",
        timeout: int = 5000,
        rst_delay: float = 1.0,
        clr_delay: float = 0.1,
        **kwargs: Any 
    ) -> None:
        """
        Initializes the generator driver.
        """
        super().__init__(resource_id)
        self.name = name or resource_id 
        self._timeout = timeout
        self._rst_delay = rst_delay
        self._clr_delay = clr_delay
        
        # MODIFICATION: Driver knows its channels.
        self.channels: List[int] = [1, 2] 
        self._instrument: Optional[visa.Resource] = None
        
        self._settings: Optional[Dict[str, Any]] = kwargs.get('settings')
        self._safety_limits: Dict[str, Any] = kwargs.get('safety_limits', {})
        self._max_amplitude: Optional[float] = self._safety_limits.get('max_amplitude_vp')
        
        # MODIFICATION: Initialize shadow state for caching
        self._shadow_state: Dict[int, Dict[str, Any]] = {}
        self._initialize_shadow_state()
        
        if self._max_amplitude is not None:
            logger.info(f"Safety limit for {self.resource_id}: Max amplitude set to {self._max_amplitude} Vp.")

        logger.info(f"Driver for KeysightEDU33212A created for resource: {self.resource_id} (Name: '{self.name}')")

    def _initialize_shadow_state(self) -> None:
        """Sets up the default internal state cache for all channels."""
        logger.debug(f"Initializing shadow state for {self.name}")
        for ch in self.channels:
            self._shadow_state[ch] = {
                'output_state': OutputState.OFF,
                'frequency': 1000.0, # Common default
                'amplitude': 0.0,
                'offset': 0.0,
                'shape': WaveformShape.SINE,
                'load_impedance': 'INFinity',
                'burst_state': False,
                'burst_num_cycles': 'INF',
                'burst_mode': 'TRIG',
                'trigger_source': TriggerSource.BUS.value
            }

    # --- Low-level Communication (Thread-Safe) ---

    def _write(self, command: str) -> None:
        """
        Sends a command to the instrument.
        MODIFICATION: This operation is now thread-safe, protected by the
        per-resource class-level lock.
        """
        if self._instrument is None:
            raise ConnectionError("Instrument not connected. Cannot write command.")
        
        # MODIFICATION: Acquire lock for all I/O
        with KeysightEDU33212A._resource_lock:
            logger.debug(f"WRITE to {self.resource_id}: {command}")
            self._instrument.write(command)

    def _query(self, command: str) -> str:
        """
        Sends a query to the instrument and returns the response.
        MODIFICATION: This operation is now thread-safe.
        """
        if self._instrument is None:
            raise ConnectionError("Instrument not connected. Cannot send query.")
        
        # MODIFICATION: Acquire lock for all I/O
        with KeysightEDU33212A._resource_lock:
            logger.debug(f"QUERY to {self.resource_id}: {command}")
            # The RLock allows this call even if the lock was already
            # acquired by a higher-level function (e.g., connect).
            return self._instrument.query(command).strip()

    # --- Connection Management (Implementation of Abstract Methods) ---

    def connect(self) -> None:
        """
        Establishes connection to the device.
        This operation is atomic and thread-safe.
        """
        if self._instrument:
            logger.warning(f"Instance '{self.name}' already connected. Ignoring connect() call.")
            return

        # Acquire lock to ensure atomic connect/check operations
        with KeysightEDU33212A._resource_lock:
            # Check if another instance has already connected to this resource
            if self.resource_id in KeysightEDU33212A._active_connections:
                # --- Subsequent Instance Path ---
                logger.info(f"Attaching '{self.name}' to existing connection for {self.resource_id}.")
                shared_data = KeysightEDU33212A._active_connections[self.resource_id]
                self._instrument = shared_data["handle"]
                shared_data["ref_count"] += 1
                logger.info(f"Attached. Ref count for {self.resource_id} is now {shared_data['ref_count']}.")
                return
            
            # --- First Instance Path ---
            try:
                logger.info(f"First instance '{self.name}' connecting to {self.resource_id}. Performing full setup...")
                
                self._instrument = KeysightEDU33212A._rm.open_resource(self.resource_id)
                self._instrument.timeout = self._timeout
                self._instrument.clear()
                time.sleep(self._clr_delay)

                # _query() will re-acquire the RLock, which is safe
                identity = self._query("*IDN?") 
                logger.info(f"Successfully connected to: {identity}")

                # _write() will also re-acquire the RLock
                self._write('*RST')
                time.sleep(self._rst_delay)
                self._write('*CLS') 
                logger.info(f"Instrument {self.resource_id} has been reset by '{self.name}'.")
                
                # MODIFICATION: Reset shadow state on *RST
                self._initialize_shadow_state()
                
                KeysightEDU33212A._active_connections[self.resource_id] = {
                    "handle": self._instrument,
                    "ref_count": 1,
                    "initialized": False
                }
                logger.info(f"Connection for {self.resource_id} registered. Ref count: 1.")

                if self._settings:
                    logger.info(f"First instance '{self.name}' applying initial settings...")
                    # This call is thread-safe (due to RLock)
                    self.initialize_device_settings(self._settings)
                else:
                    logger.warning(f"First instance '{self.name}' connected, but no 'settings' were provided. Skipping one-time initialization.")

            except visa.VisaIOError as e:
                self._instrument = None
                logger.error(f"Failed to connect '{self.name}' to {self.resource_id}: {e}")
                raise ConnectionError(f"VISA I/O Error connecting to {self.resource_id}") from e
        
    def disconnect(self) -> None:
        """
        Disconnects the instance.
        This operation is atomic and thread-safe.
        """
        if not self._instrument:
            logger.warning(f"Instance '{self.name}' already disconnected. Ignoring disconnect() call.")
            return

        with KeysightEDU33212A._resource_lock:
            shared_data = KeysightEDU33212A._active_connections.get(self.resource_id)

            if not shared_data or shared_data["handle"] != self._instrument:
                logger.warning(f"Disconnecting '{self.name}' from an unmanaged or inconsistent resource. Forcing local disconnect.")
                try:
                    self._instrument.close()
                except visa.VisaIOError as e:
                    logger.error(f"Error during forced disconnect for '{self.name}': {e}")
                finally:
                    self._instrument = None
                return

            # --- Managed Disconnect Path ---
            shared_data["ref_count"] -= 1
            logger.info(f"Detaching instance '{self.name}'. Ref count for {self.resource_id} is now {shared_data['ref_count']}.")

            if shared_data["ref_count"] == 0:
                # --- Last Instance Path ---
                logger.info(f"Last instance '{self.name}' disconnecting. Closing VISA resource {self.resource_id}...")
                try:
                    # Turn off outputs (safe due to RLock)
                    self.set_output_state(1, OutputState.OFF)
                    self.set_output_state(2, OutputState.OFF)
                    self._instrument.clear()
                    time.sleep(self._clr_delay)
                    self._instrument.close()
                    logger.info(f"Resource {self.resource_id} closed successfully.")
                except visa.VisaIOError as e:
                    logger.error(f"Error during final disconnect of {self.resource_id}: {e}")
                finally:
                    del KeysightEDU33212A._active_connections[self.resource_id]
                    self._instrument = None
            else:
                # --- Subsequent Instance Path ---
                self._instrument = None
                logger.debug(f"Instance '{self.name}' detached. Resource {self.resource_id} remains open.")

    # --- Instrument Status ---
    
    @property
    def is_connected(self) -> bool:
        """MODIFICATION: Implementation of abstract property."""
        return self._instrument is not None

    # --- Instrument Control (Implementation of Abstract Methods) ---
    # All methods below are now thread-safe as they call _write/_query
    # MODIFICATION: All 'set' methods now update the shadow state.

    def set_output_state(self, channel: int, state: OutputState) -> None:
        self._write(f':OUTPut{channel}:STATe {state.value}')
        self._shadow_state[channel]['output_state'] = state

    def set_frequency(self, channel: int, frequency: float) -> None:
        self._write(f':SOURce{channel}:FREQuency {frequency:.4f}')
        self._shadow_state[channel]['frequency'] = frequency

    def set_amplitude(self, channel: int, amplitude: float) -> None:
        """Sets the peak-to-peak voltage amplitude (Vp)."""
        if self._max_amplitude is not None and amplitude > self._max_amplitude:
            err_msg = (
                f"SAFETY LIMIT VIOLATION for {self.resource_id}: "
                f"Attempted to set amplitude to {amplitude:.4f} Vp, "
                f"which exceeds the limit of {self._max_amplitude:.4f} Vp."
            )
            logger.error(err_msg)
            raise ValueError(err_msg)
        self._write(f':SOURce{channel}:VOLTage {amplitude:.4f}')
        self._shadow_state[channel]['amplitude'] = amplitude

    def set_offset(self, channel: int, offset: float) -> None:
        self._write(f':SOURce{channel}:VOLTage:OFFSet {offset:.4f}')
        self._shadow_state[channel]['offset'] = offset

    def set_waveform_shape(self, channel: int, shape: WaveformShape) -> None:
        self._write(f':SOURce{channel}:FUNCtion {shape.value}')
        self._shadow_state[channel]['shape'] = shape

    # --- Granular Getters (Perform I/O) ---
    def get_output_state(self, channel: int) -> OutputState:
        state_str = self._query(f":OUTPut{channel}:STATe?")
        return OutputState.ON if '1' in state_str or 'ON' in state_str.upper() else OutputState.OFF

    def get_frequency(self, channel: int) -> float:
        return float(self._query(f":SOURce{channel}:FREQuency?"))

    def get_amplitude(self, channel: int) -> float:
        return float(self._query(f":SOURce{channel}:VOLTage?"))

    def get_offset(self, channel: int) -> float:
        return float(self._query(f":SOURce{channel}:VOLTage:OFFSet?"))

    # --- NEW: Logical (Cached) State Getters (No I/O) ---

    def get_logical_output_state(self, channel: int) -> OutputState:
        """Gets the cached (expected) output state without a query."""
        return self._shadow_state[channel]['output_state']

    def get_logical_frequency(self, channel: int) -> float:
        """Gets the cached (expected) frequency without a query."""
        return self._shadow_state[channel]['frequency']

    def get_logical_amplitude(self, channel: int) -> float:
        """Gets the cached (expected) amplitude without a query."""
        return self._shadow_state[channel]['amplitude']

    def get_logical_offset(self, channel: int) -> float:
        """Gets the cached (expected) offset without a query."""
        return self._shadow_state[channel]['offset']

    def get_logical_waveform_shape(self, channel: int) -> WaveformShape:
        """Gets the cached (expected) waveform shape without a query."""
        return self._shadow_state[channel]['shape']

    def get_logical_channel_state(self, channel: int) -> Dict[str, Any]:
        """
        Gets the full cached (expected) state dictionary for a channel.
        Returns a copy to prevent mutation of the internal state.
        """
        return self._shadow_state[channel].copy()
        
    def get_logical_state(self) -> Dict[int, Dict[str, Any]]:
        """
        Gets the full cached (expected) state for all channels.
        Returns a deep-enough copy to prevent mutation.
        """
        return {ch: state.copy() for ch, state in self._shadow_state.items()}

    # --- High-Level and Utility Methods ---

    def apply_sinusoid(self, channel: int, frequency: float, amplitude: float, offset: float = 0.0) -> None:
        """Configures the source to output a sinusoid with specified parameters."""
        if self._max_amplitude is not None and amplitude > self._max_amplitude:
            err_msg = (
                f"SAFETY LIMIT VIOLATION for {self.resource_id}: "
                f"Attempted to apply sinusoid with amplitude {amplitude:.4f} Vp, "
                f"which exceeds the limit of {self._max_amplitude:.4f} Vp."
            )
            logger.error(err_msg)
            raise ValueError(err_msg)
        
        self._write(f':SOURce{channel}:APPLy:SINusoid {frequency},{amplitude:.4f},{offset:.4f}')
        
        # MODIFICATION: Update shadow state
        self._shadow_state[channel]['shape'] = WaveformShape.SINE
        self._shadow_state[channel]['frequency'] = frequency
        self._shadow_state[channel]['amplitude'] = amplitude
        self._shadow_state[channel]['offset'] = offset
        
        logger.info(f"Applied Sinusoid to Ch{channel}: {frequency} Hz, {amplitude:.4f} Vp, {offset:.4f} V")

    def initialize_device_settings(self, config: Dict[str, Any]) -> None:
        """
        Applies a dictionary of default settings to the instrument.
        This operation is thread-safe (uses RLock).
        MODIFICATION: This method now populates the shadow state.
        """
        if self._instrument is None:
            raise ConnectionError("Instrument not connected. Cannot initialize settings.")
            
        if not config:
            logger.warning(f"Initialization skipped for {self.resource_id}: No configuration provided.")
            return

        with KeysightEDU33212A._resource_lock:
            shared_data = KeysightEDU33212A._active_connections.get(self.resource_id)

            if not shared_data or shared_data["handle"] != self._instrument:
                logger.warning(f"Cannot initialize settings: No managed connection found for {self.resource_id}.")
                return

            if shared_data["initialized"]:
                logger.warning(f"Settings for {self.resource_id} have already been initialized. Skipping.")
                return
            
            logger.info(f"Applying one-time initial settings for {self.resource_id} (by instance '{self.name}')...")
            try:
                self._write('SYSTem:BEEPer:STATe OFF')
                
                # Read config values with defaults
                load_impedance = config.get('load_impedance', 'INFinity')
                function_shape = WaveformShape(config.get('function', 'SIN').upper())
                burst_state = bool(config.get('burst_state', True))
                burst_num_cycles = config.get('burst_num_cycles', 'INF')
                burst_mode = config.get('burst_mode', 'TRIG')
                trigger_source = config.get('trigger_source', TriggerSource.BUS.value)

                for ch in self.channels:
                    # These methods update shadow state automatically
                    self.set_output_state(ch, OutputState.OFF)
                    self.set_waveform_shape(ch, function_shape)
                    self.set_amplitude(ch, 0.0) # Safety: init to 0V

                    # These write directly and require manual state update
                    self._write(f":OUTPut{ch}:LOAD {load_impedance}")
                    self._shadow_state[ch]['load_impedance'] = load_impedance
                    
                    self._write(f":SOURce{ch}:BURSt:STATe {1 if burst_state else 0}")
                    self._shadow_state[ch]['burst_state'] = burst_state
                    
                    self._write(f":SOURce{ch}:BURSt:NCYCles {burst_num_cycles}")
                    self._shadow_state[ch]['burst_num_cycles'] = burst_num_cycles
                    
                    self._write(f":SOURce{ch}:BURSt:MODE {burst_mode}")
                    self._shadow_state[ch]['burst_mode'] = burst_mode
                    
                    self._write(f':TRIGger{ch}:SOURce {trigger_source}') 
                    self._shadow_state[ch]['trigger_source'] = trigger_source
                    
                    self._write(f':OUTPut{ch}:TRIGger:STATe ON')
                    
                    logger.debug(f"Defaults applied to channel {ch} for {self.name}.")
                
                shared_data["initialized"] = True
                logger.info(f"One-time initialization complete for {self.resource_id}.")

            except visa.VisaIOError as e:
                logger.error(f"Failed to apply settings for {self.resource_id}: {e}")
                raise ConnectionError(f"VISA I/O Error during settings initialization for {self.resource_id}") from e
    
    def enable_channels(self) -> None:
        """
        Enables the physical output state for all channels.
        MODIFICATION: Now correctly uses self.channels.
        """
        logger.info(f"Activating output state for channels {self.channels} on {self.name}.")
        for ch in self.channels:
            self.set_output_state(ch, OutputState.ON)
    
    def disable_channels(self) -> None:
        """
        Disables the physical output state for all channels.
        MODIFICATION: Now correctly uses self.channels.
        """
        logger.info(f"Deactivating output state for channels {self.channels} on {self.name}.")
        for ch in self.channels:
            self.set_output_state(ch, OutputState.OFF)
    
    def send_software_trigger(self) -> None:
            """
            Sends a software trigger (*TRG).
            MODIFICATION: Checks the cached self._shadow_state for all channels.
            """
            logger.info(f"Sending global software trigger (*TRG) to {self.name}.")
            has_bus_trigger = False
            
            for ch in self.channels:
                ch_trigger_source = self.get_logical_channel_state(ch).get('trigger_source')
                
                if ch_trigger_source == TriggerSource.BUS.value:
                    has_bus_trigger = True
                else:
                    logger.warning(
                        f"Channel {ch} on {self.name} is set to "
                        f"'{ch_trigger_source}', not 'BUS'. "
                        f"It may not respond to this software trigger."
                    )
            
            if not has_bus_trigger:
                    logger.warning(
                        f"send_software_trigger() called on {self.name}, "
                        f"but no channel is set to 'BUS' trigger. "
                        f"Sending *TRG command anyway."
                    )
            
            self._write('*TRG')

    def abort(self) -> None:
        """Aborts the current waveform generation."""
        logger.info(f"Sending abort command to {self.name}.")
        self._write(':ABORt')

    def beep(self) -> None:
        """Triggers the system beeper for auditory feedback."""
        self._write('SYSTem:BEEPer:IMMediate')

    def wait_opc(self) -> bool:
        """Waits for the instrument to complete all pending operations."""
        try:
            self._query("*OPC?")
            return True
        except visa.VisaIOError as e:
            logger.warning(f"Error during *OPC? query for {self.name}: {e}")
            return False

    # --- Instrument Status (Performs I/O) ---

    def get_status(self) -> Dict[str, Any]:
        """
        Queries the instrument for the *actual* status of all channels.
        Note: This performs I/O and does not use the cached logical state.
        """
        if not self.is_connected:
            return {"connection": "disconnected"}

        try:
            status = {"connection": "active", "identity": self._query("*IDN?")}
            for ch in self.channels: # Use self.channels
                try:
                    ch_status = {
                        "output_state": self.get_output_state(ch).value,
                        "waveform": self._query(f":SOURce{ch}:FUNCtion?"),
                        "frequency_hz": self.get_frequency(ch),
                        "amplitude_Vp": self.get_amplitude(ch),
                        "offset_v": self.get_offset(ch),
                    }
                    status[f'channel_{ch}'] = ch_status
                except (visa.VisaIOError, ValueError) as e:
                    status[f'channel_{ch}'] = f"Error querying status: {e}"
            
            # Also include the full logical state for comparison
            status['logical_state'] = self.get_logical_state()
            return status
            
        except Exception as e:
            logger.error(f"Failed to get_status for {self.name}: {e}")
            return {"connection": "error", "detail": str(e)}