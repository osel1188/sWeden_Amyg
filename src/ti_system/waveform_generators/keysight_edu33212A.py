import pyvisa as visa
import time
import logging
from typing import  Optional, Any, Dict

from .waveform_generator import (
    AbstractWaveformGenerator, 
    OutputState,
    WaveformShape
)

# Setup a standard logger. The application, not the driver, decides where logs go.
log = logging.getLogger(__name__)

class KeysightEDU33212A(AbstractWaveformGenerator):
    """
    A concrete implementation for a Keysight EDU33220A series waveform generator.

    This class focuses SOLELY on translating the abstract interface methods into
    the specific SCPI commands for this instrument. It does not handle logging
    configuration or application-level logic.
    """

    def __init__(self, resource_id: str, timeout: int = 10000, rst_delay: float = 1.0) -> None:
        """
        Initializes the generator driver.

        Args:
            resource_id (str): The VISA resource identifier.
            timeout (int): The VISA communication timeout in milliseconds.
            rst_delay (float): The delay in seconds after a reset command.
        """
        super().__init__(resource_id)
        self._timeout = timeout
        self._rst_delay = rst_delay
        self._instrument: Optional[visa.Resource] = None
        self._rm = visa.ResourceManager()
        log.info(f"Driver for KeysightEDU33212A created for resource: {self.resource_id}")

    # --- Low-level Communication (Internal) ---

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
        """Establishes connection to the device and resets it."""
        if self._instrument:
            log.warning("Already connected. Ignoring connect() call.")
            return
        try:
            log.info(f"Attempting to connect to {self.resource_id}...")
            self._instrument = self._rm.open_resource(self.resource_id)
            self._instrument.timeout = self._timeout
            self._instrument.clear()
            
            identity = self._query("*IDN?")
            log.info(f"Successfully connected to: {identity}")
            
            self._write('*RST')
            time.sleep(self._rst_delay)
            self._write('*CLS') # Clear status
            log.info(f"Instrument {self.resource_id} has been reset.")
        except visa.VisaIOError as e:
            self._instrument = None
            log.error(f"Failed to connect to {self.resource_id}: {e}")
            # Raise a standard exception to be handled by the application
            raise ConnectionError(f"VISA I/O Error connecting to {self.resource_id}") from e

    def disconnect(self) -> None:
        """Turns off outputs and closes the VISA connection."""
        if self._instrument:
            log.info(f"Disconnecting from {self.resource_id}...")
            try:
                # Turn off outputs as a safety measure
                self.set_output_state(1, OutputState.OFF)
                self.set_output_state(2, OutputState.OFF)
                self._instrument.clear()
                self._instrument.close()
                log.info("Disconnected successfully.")
            except visa.VisaIOError as e:
                log.error(f"Error during disconnect: {e}")
            finally:
                self._instrument = None

    # --- Instrument Control (Implementation of Abstract Methods) ---

    def set_output_state(self, channel: int, state: OutputState) -> None:
        self._write(f':OUTPut{channel}:STATe {state.value}')

    def set_frequency(self, channel: int, frequency: float) -> None:
        self._write(f':SOURce{channel}:FREQuency {frequency:.4f}')

    def set_amplitude(self, channel: int, amplitude: float) -> None:
        """Sets the peak-to-peak voltage amplitude (Vpp)."""
        self._write(f':SOURce{channel}:VOLTage {amplitude:.4f}')
        
    def set_offset(self, channel: int, offset: float) -> None:
        self._write(f':SOURce{channel}:VOLTage:OFFSet {offset:.4f}')

    def set_waveform_shape(self, channel: int, shape: WaveformShape) -> None:
        self._write(f':SOURce{channel}:FUNCtion {shape.value}')

    def get_status(self) -> Dict[str, Any]:
        """Queries the instrument for the status of both channels."""
        if self._instrument is None:
            return {"connection": "disconnected"}

        status = {"connection": "active", "identity": self._query("*IDN?")}
        for ch in [1, 2]:
            try:
                ch_status = {
                    "output_state": self._query(f":OUTPut{ch}:STATe?"),
                    "waveform": self._query(f":SOURce{ch}:FUNCtion?"),
                    "frequency_hz": float(self._query(f":SOURce{ch}:FREQuency?")),
                    "amplitude_vpp": float(self._query(f":SOURce{ch}:VOLTage?")),
                    "offset_v": float(self._query(f":SOURce{ch}:VOLTage:OFFSet?")),
                }
                status[f'channel_{ch}'] = ch_status
            except (visa.VisaIOError, ValueError) as e:
                 status[f'channel_{ch}'] = f"Error querying status: {e}"
        return status
