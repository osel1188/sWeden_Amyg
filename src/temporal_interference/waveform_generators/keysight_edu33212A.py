# --- Conditional VISA Import ---
from .config import USE_MOCK

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
# MODIFICATION: Import RLock instead of Lock for re-entrant capability
import threading
from typing import Optional, Any, Dict, List

from .waveform_generator import (
    AbstractWaveformGenerator,
    OutputState,
    WaveformShape
)

# Setup a standard logger. The application, not the driver, decides where logs go.
log = logging.getLogger(__name__)

class KeysightEDU33212A(AbstractWaveformGenerator, model_id="KeysightEDU33212A"):
    """
    A concrete implementation for a Keysight EDU33220A series waveform generator.

    This class translates the abstract interface methods into SCPI commands
    and provides high-level control functionalities.
    
    It uses a class-level, thread-safe connection manager to ensure that
    only the first instance connecting to a specific resource_id performs
    an instrument reset (*RST). Subsequent instances attach to the
    existing handle.
    """
    
    # --- Class-level shared resource management ---
    _rm = visa.ResourceManager()
    _active_connections: Dict[str, Dict[str, Any]] = {}
    # MODIFICATION: Use RLock to prevent deadlock when connect() calls
    # initialize_device_settings(), as both acquire the lock.
    _resource_lock = threading.RLock()
    # ----------------------------------------------

    def __init__(
        self,
        resource_id: str,
        name: str = "",
        timeout: int = 10000,
        rst_delay: float = 1.0,
        clr_delay: float = 0.1,
        **kwargs: Any 
    ) -> None:
        """
        Initializes the generator driver.

        Args:
            resource_id (str): The VISA resource identifier.
            name (str, optional): A user-friendly name for logging purposes. Defaults to "".
            timeout (int): The VISA communication timeout in milliseconds.
            rst_delay (float): The delay in seconds after a reset command.
            clr_delay (float): The delay in seconds after a clear command.
            **kwargs:
                settings (Dict): Configuration dictionary for one-time initialization.
                safety_limits (Dict): Dictionary of safety limits, e.g.,
                                      {'max_amplitude_Vp': 5.0}.
        """
        super().__init__(resource_id)
        self.name = name or resource_id # Use resource_id if name is empty
        self._timeout = timeout
        self._rst_delay = rst_delay
        self._clr_delay = clr_delay
        self.channels: List[int] = []
        self._instrument: Optional[visa.Resource] = None
        
        # The config dict for initialize_device_settings
        self._settings: Optional[Dict[str, Any]] = kwargs.get('settings')
        # Safety limits (e.g., {'max_amplitude_Vp': 5.0})
        self._safety_limits: Dict[str, Any] = kwargs.get('safety_limits', {})
        self._max_amplitude: Optional[float] = self._safety_limits.get('max_amplitude_vp')
        
        if self._max_amplitude is not None:
            log.info(f"Safety limit for {self.resource_id}: Max amplitude set to {self._max_amplitude} Vp.")
        # -----------------------------------------------------------------

        log.info(f"Driver for KeysightEDU33212A created for resource: {self.resource_id} (Name: '{self.name}')")


    # --- Low-level Communication ---

    def _write(self, command: str) -> None:
        """Sends a command to the instrument."""
        if self._instrument is None:
            raise ConnectionError("Instrument not connected. Cannot write command.")
        log.debug(f"WRITE to {self.resource_id}: {command}")
        self._instrument.write(command)

    def _query(self, command: str) -> str:
        """Sends a query to the instrument and returns the response."""
        if self._instrument is None:
            raise ConnectionError("Instrument not connected. Cannot send query.")
        log.debug(f"QUERY to {self.resource_id}: {command}")
        return self._instrument.query(command).strip()

    # --- Connection Management (Implementation of Abstract Methods) ---

    def connect(self) -> None:
        """
        Establishes connection to the device.

        If this is the first instance for this resource_id, it opens
        the connection, resets the instrument, and applies initial settings
        if they were provided during construction.
        If an existing connection is found, it attaches to it without
        resetting.
        """
        if self._instrument:
            log.warning(f"Instance '{self.name}' already connected. Ignoring connect() call.")
            return

        # Acquire lock to ensure atomic connect/check operations
        with KeysightEDU33212A._resource_lock:
            # Check if another instance has already connected to this resource
            if self.resource_id in KeysightEDU33212A._active_connections:
                # --- Subsequent Instance Path ---
                log.info(f"Attaching '{self.name}' to existing connection for {self.resource_id}.")
                shared_data = KeysightEDU33212A._active_connections[self.resource_id]
                
                # Assign the shared handle to this instance
                self._instrument = shared_data["handle"]
                
                # Increment the reference count
                shared_data["ref_count"] += 1
                
                log.info(f"Attached. Ref count for {self.resource_id} is now {shared_data['ref_count']}.")
                # Skip reset, clear, and IDN query as it was done by the first instance
                return
            
            # --- First Instance Path ---
            try:
                log.info(f"First instance '{self.name}' connecting to {self.resource_id}. Performing full setup...")
                
                # Use the class-level resource manager
                self._instrument = KeysightEDU33212A._rm.open_resource(self.resource_id)
                self._instrument.timeout = self._timeout
                self._instrument.clear()
                time.sleep(self._clr_delay)

                identity = self._query("*IDN?")
                log.info(f"Successfully connected to: {identity}")

                self._write('*RST')
                time.sleep(self._rst_delay)
                self._write('*CLS') # Clear status
                log.info(f"Instrument {self.resource_id} has been reset by '{self.name}'.")
                
                # Store the new handle and set initial ref_count
                KeysightEDU33212A._active_connections[self.resource_id] = {
                    "handle": self._instrument,
                    "ref_count": 1,
                    "initialized": False
                }
                log.info(f"Connection for {self.resource_id} registered. Ref count: 1.")

                # --- MODIFICATION: Auto-initialize settings on first connect ---
                if self._settings:
                    log.info(f"First instance '{self.name}' applying initial settings...")
                    # This call is thread-safe (due to RLock) and respects the
                    # 'initialized' flag check within the method itself.
                    self.initialize_device_settings(self._settings)
                else:
                    log.warning(f"First instance '{self.name}' connected, but no 'settings' were provided. Skipping one-time initialization.")
                # --------------------------------------------------------------

            except visa.VisaIOError as e:
                self._instrument = None
                log.error(f"Failed to connect '{self.name}' to {self.resource_id}: {e}")
                raise ConnectionError(f"VISA I/O Error connecting to {self.resource_id}") from e
        
    def disconnect(self) -> None:
        """
        Disconnects the instance.
        
        If this is the last instance using the connection, the VISA
        resource is safely closed. Otherwise, it just detaches this
        instance.
        """
        if not self._instrument:
            log.warning(f"Instance '{self.name}' already disconnected. Ignoring disconnect() call.")
            return

        # Acquire lock to ensure atomic disconnect/check operations
        with KeysightEDU33212A._resource_lock:
            # Check if the connection is managed by the class
            shared_data = KeysightEDU33212A._active_connections.get(self.resource_id)

            if not shared_data or shared_data["handle"] != self._instrument:
                log.warning(f"Disconnecting '{self.name}' from an unmanaged or inconsistent resource. Forcing local disconnect.")
                try:
                    self._instrument.close()
                except visa.VisaIOError as e:
                    log.error(f"Error during forced disconnect for '{self.name}': {e}")
                finally:
                    self._instrument = None
                return

            # --- Managed Disconnect Path ---
            
            # Decrement reference count
            shared_data["ref_count"] -= 1
            log.info(f"Detaching instance '{self.name}'. Ref count for {self.resource_id} is now {shared_data['ref_count']}.")

            if shared_data["ref_count"] == 0:
                # --- Last Instance Path ---
                log.info(f"Last instance '{self.name}' disconnecting. Closing VISA resource {self.resource_id}...")
                try:
                    # Turn off outputs as a safety measure
                    self.set_output_state(1, OutputState.OFF)
                    self.set_output_state(2, OutputState.OFF)
                    self._instrument.clear()
                    time.sleep(self._clr_delay)
                    self._instrument.close()
                    log.info(f"Resource {self.resource_id} closed successfully.")
                except visa.VisaIOError as e:
                    log.error(f"Error during final disconnect of {self.resource_id}: {e}")
                finally:
                    # Remove from active connections
                    del KeysightEDU33212A._active_connections[self.resource_id]
                    self._instrument = None
            else:
                # --- Subsequent Instance Path ---
                # Not the last instance, just detach this instance
                self._instrument = None
                log.debug(f"Instance '{self.name}' detached. Resource {self.resource_id} remains open.")

    # --- Instrument Control (Implementation of Abstract Methods) ---

    def set_output_state(self, channel: int, state: OutputState) -> None:
        self._write(f':OUTPut{channel}:STATe {state.value}')

    def set_frequency(self, channel: int, frequency: float) -> None:
        self._write(f':SOURce{channel}:FREQuency {frequency:.4f}')

    def set_amplitude(self, channel: int, amplitude: float) -> None:
        """Sets the peak-to-peak voltage amplitude (Vp)."""
        # --- MODIFICATION: Safety Limit Check ---
        if self._max_amplitude is not None and amplitude > self._max_amplitude:
            err_msg = (
                f"SAFETY LIMIT VIOLATION for {self.resource_id}: "
                f"Attempted to set amplitude to {amplitude:.4f} Vp, "
                f"which exceeds the limit of {self._max_amplitude:.4f} Vp."
            )
            log.error(err_msg)
            raise ValueError(err_msg)
        # ----------------------------------------
        self._write(f':SOURce{channel}:VOLTage {amplitude:.4f}')

    def set_offset(self, channel: int, offset: float) -> None:
        self._write(f':SOURce{channel}:VOLTage:OFFSet {offset:.4f}')

    def set_waveform_shape(self, channel: int, shape: WaveformShape) -> None:
        self._write(f':SOURce{channel}:FUNCtion {shape.value}')

    # --- Granular Getters ---
    def get_output_state(self, channel: int) -> OutputState:
        """Queries the output state of a specific channel."""
        state_str = self._query(f":OUTPut{channel}:STATe?")
        # Check for either '1' or 'ON' (case-insensitive) for the ON state.
        return OutputState.ON if '1' in state_str or 'ON' in state_str.upper() else OutputState.OFF

    def get_frequency(self, channel: int) -> float:
        """Queries the frequency of a specific channel."""
        return float(self._query(f":SOURce{channel}:FREQuency?"))

    def get_amplitude(self, channel: int) -> float:
        """Queries the peak-to-peak voltage amplitude (Vp) of a specific channel."""
        return float(self._query(f":SOURce{channel}:VOLTage?"))

    def get_offset(self, channel: int) -> float:
        """Queries the DC offset voltage of a specific channel."""
        return float(self._query(f":SOURce{channel}:VOLTage:OFFSet?"))

    # --- High-Level and Utility Methods ---

    def apply_sinusoid(self, channel: int, frequency: float, amplitude: float, offset: float = 0.0) -> None:
        """Configures the source to output a sinusoid with specified parameters."""
        # --- MODIFICATION: Safety Limit Check ---
        if self._max_amplitude is not None and amplitude > self._max_amplitude:
            err_msg = (
                f"SAFETY LIMIT VIOLATION for {self.resource_id}: "
                f"Attempted to apply sinusoid with amplitude {amplitude:.4f} Vp, "
                f"which exceeds the limit of {self._max_amplitude:.4f} Vp."
            )
            log.error(err_msg)
            raise ValueError(err_msg)
        # ----------------------------------------
        
        # Using a single APPLY command is often more efficient on the instrument side.
        self._write(f':SOURce{channel}:APPLy:SINusoid {frequency},{amplitude:.4f},{offset:.4f}')
        log.info(f"Applied Sinusoid to Ch{channel}: {frequency} Hz, {amplitude:.4f} Vp, {offset:.4f} V")

    def initialize_device_settings(self, config: Dict[str, Any]) -> None:
        """
        Applies a dictionary of default settings to the instrument.
        
        This operation is thread-safe and will only be executed *once*
        per active connection session (i.e., by the first instance
        that calls it, or automatically on first connect).
        """
        if self._instrument is None:
            raise ConnectionError("Instrument not connected. Cannot initialize settings.")
            
        if not config:
            log.warning(f"Initialization skipped for {self.resource_id}: No configuration provided.")
            return

        # Acquire lock to ensure atomic check/set of the initialized flag
        with KeysightEDU33212A._resource_lock:
            shared_data = KeysightEDU33212A._active_connections.get(self.resource_id)

            if not shared_data or shared_data["handle"] != self._instrument:
                log.warning(f"Cannot initialize settings: No managed connection found for {self.resource_id}.")
                return

            if shared_data["initialized"]:
                log.warning(f"Settings for {self.resource_id} have already been initialized. Skipping.")
                return
            
            # --- Proceed with Initialization ---
            log.info(f"Applying one-time initial settings for {self.resource_id} (by instance '{self.name}')...")
            try:
                self.channels = config.get('source_channels', [1, 2])
                for ch in self.channels:
                    self.set_output_state(ch, OutputState.OFF)
                    self._write(f":OUTPut{ch}:LOAD {config.get('load_impedance', 'INFinity')}")
                    self.set_waveform_shape(ch, WaveformShape(config.get('function', 'SIN').upper()))
                    self._write(f":SOURce{ch}:FUNCtion {config.get('function', 'SIN')}")
                    self._write(f":SOURce{ch}:BURSt:STATe {1 if config.get('burst_state', True) else 0}")
                    self._write(f":SOURce{ch}:BURSt:NCYCles {config.get('burst_num_cycles', 'INF')}")
                    self._write(f":SOURce{ch}:BURSt:MODE {config.get('burst_mode', 'TRIG')}")
                    log.debug(f"Defaults applied to channel {ch} for {self.name}.")
                
                # --- Set flag AFTER successful initialization ---
                shared_data["initialized"] = True
                log.info(f"One-time initialization complete for {self.resource_id}.")

            except visa.VisaIOError as e:
                log.error(f"Failed to apply settings for {self.resource_id}: {e}")
                # Do not set initialized = True if it failed
                raise ConnectionError(f"VISA I/O Error during settings initialization for {self.resource_id}") from e

    def set_trigger_source_bus(self) -> None:
        """Sets the trigger source to BUS (software/internal)."""
        for ch in self.channels:
            self._write(f':TRIGger{ch}:SOURce BUS')
            log.debug(f"Device '{self.name}': Channel {ch} trigger source set to BUS")
        self.enable_output_trigger()
    
    def set_trigger_source_external(self) -> None:
        """Sets the trigger source to EXT (external hardware trigger)."""
        for ch in self.channels:
            self._write(f':TRIGger{ch}:SOURce EXT')
            log.debug(f"Device '{self.name}': Channel {ch} trigger source set to EXT")
        self.enable_output_trigger()
    
    def set_output_trigger(self, state: str) -> None:
        """
        Sets the output trigger signal state for all channels.
        This configures the instrument to start channels when trigger mode is ON.
        Args:
            state (str): The desired trigger state. Must be 'ON' or 'OFF'
                         (case-insensitive).
        """
        # Normalize and validate state
        norm_state = state.upper().strip()
        if norm_state not in ('ON', 'OFF'):
            raise ValueError(f"Invalid state '{state}'. Must be 'ON' or 'OFF'.")
        
        # Determine log message based on normalized state
        log_msg = "enabled" if norm_state == 'ON' else "disabled"
        
        for ch in self.channels:
            self._write(f':OUTPut{ch}:TRIGger:STATe {norm_state}')
            log.debug(f"Device '{self.name}': Channel {ch} {log_msg} for output trigger.")

    def enable_output_trigger(self) -> None:
        self.set_output_trigger('ON')

    def disable_output_trigger(self) -> None:
        self.set_output_trigger('OFF')
    
    def trigger(self) -> None:
        """
        Sends a software trigger (*TRG). 
        It will work only if the device is set to source bus trigger.
        """
        log.info(f"Sending software trigger to {self.name}.")
        self._write('*TRG')

    def abort(self) -> None:
        """Aborts the current waveform generation."""
        log.info(f"Sending abort command to {self.name}.")
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
            log.warning(f"Error during *OPC? query for {self.name}: {e}")
            return False

    # --- Instrument Status ---

    def get_status(self) -> Dict[str, Any]:
        """Queries the instrument for the status of both channels."""
        if self._instrument is None:
            return {"connection": "disconnected"}

        status = {"connection": "active", "identity": self._query("*IDN?")}
        for ch in [1, 2]:
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
        return status