# File: mock_visa.py
# Description: A mock 'pyvisa' library for intercepting and simulating
#              hardware communication at the SCPI level.

import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# --- Mock VISA Exception ---
class VisaIOError(IOError):
    """Mock version of pyvisa.VisaIOError."""
    def __init__(self, description: str, *args, **kwargs):
        self.description = description
        super().__init__(description)

# --- Default Instrument State ---
def get_default_state() -> Dict[str, Any]:
    """Returns the default state of a single channel."""
    return {
        "output_state": "OFF",
        "function": "SIN",
        "frequency": 1000.0,
        "amplitude_vpp": 1.0,
        "offset_v": 0.0,
    }

# --- Mock Resource (Simulates the Instrument) ---
class MockResource:
    """
    Simulates a VISA resource (the instrument itself).
    Parses SCPI commands to update an internal state.
    """
    def __init__(self, resource_id: str):
        self.resource_id = resource_id
        self._timeout: int = 5000
        # State holds the simulated state for channels 1 and 2
        self._state: Dict[int, Dict[str, Any]] = {
            1: get_default_state(),
            2: get_default_state(),
        }
        logger.info(f"MockResource created for {self.resource_id}")

    # --- Connection Methods (Mocked) ---
    def clear(self) -> None:
        logger.debug(f"MockResource.clear() called")
        pass # No operation

    def close(self) -> None:
        logger.debug(f"MockResource.close() called")
        pass # No operation

    @property
    def timeout(self) -> int:
        return self._timeout

    @timeout.setter
    def timeout(self, value: int) -> None:
        logger.debug(f"MockResource.timeout set to {value}")
        self._timeout = value

    # --- Core SCPI Simulation ---

    def write(self, command: str) -> None:
        """
Setting to a mock (Fake) implementation of the Keysight generator for testing.
        This method parses SCPI "set" commands and updates the internal state.
        """
        logger.debug(f"MOCK WRITE: {command}")
        
        # --- System Commands ---
        if command == '*RST':
            self._state = { 1: get_default_state(), 2: get_default_state() }
            return
        if command in ('*CLS', '*TRG', ':ABORt', 'SYSTem:BEEPer:IMMediate'):
            return # Acknowledge but do nothing

        # --- Channel-Specific Commands (Regex) ---
        # :SOURce[ch]:FREQuency [val]
        m = re.match(r':SOURce(\d):FREQuency (.*)', command, re.IGNORECASE)
        if m:
            self._state[int(m.group(1))]['frequency'] = float(m.group(2))
            return

        # :SOURce[ch]:VOLTage:OFFSet [val]
        m = re.match(r':SOURce(\d):VOLTage:OFFSet (.*)', command, re.IGNORECASE)
        if m:
            self._state[int(m.group(1))]['offset_v'] = float(m.group(2))
            return
            
        # :SOURce[ch]:VOLTage [val] (Amplitude)
        m = re.match(r':SOURce(\d):VOLTage (.*)', command, re.IGNORECASE)
        if m:
            self._state[int(m.group(1))]['amplitude_vpp'] = float(m.group(2))
            return

        # :SOURce[ch]:FUNCtion [shape]
        m = re.match(r':SOURce(\d):FUNCtion (.*)', command, re.IGNORECASE)
        if m:
            self._state[int(m.group(1))]['function'] = m.group(2).upper()
            return

        # :OUTPut[ch]:STATe [state]
        m = re.match(r':OUTPut(\d):STATe (.*)', command, re.IGNORECASE)
        if m:
            state = m.group(2).upper()
            self._state[int(m.group(1))]['output_state'] = 'ON' if state in ('ON', '1') else 'OFF'
            return

        # :SOURce[ch]:APPLy:SINusoid [freq],[amp],[off]
        m = re.match(r':SOURce(\d):APPLy:SINusoid (.*)', command, re.IGNORECASE)
        if m:
            ch = int(m.group(1))
            params = m.group(2).split(',')
            self._state[ch]['function'] = 'SIN'
            self._state[ch]['frequency'] = float(params[0])
            self._state[ch]['amplitude_vpp'] = float(params[1])
            self._state[ch]['offset_v'] = float(params[2])
            return

        # Add regex for other 'write' commands here...
        # e.g., :OUTPut[ch]:LOAD, :SOURce[ch]:BURSt:STATe, etc.

        logger.warning(f"Unhandled MOCK WRITE command: {command}")

    def query(self, command: str) -> str:
        """
        Simulates SCPI "query" commands.
        This method parses SCPI queries and returns a string from the internal state.
        """
        logger.debug(f"MOCK QUERY: {command}")
        
        # --- System Queries ---
        if command == '*IDN?':
            return "MOCK,KEYSIGHT,EDU33212A,SCPI_SIM,FW1.0"
        if command == '*OPC?':
            return '1' # Operation complete

        # --- Channel-Specific Queries (Regex) ---
        # :SOURce[ch]:FREQuency?
        m = re.match(r':SOURce(\d):FREQuency\?', command, re.IGNORECASE)
        if m:
            return str(self._state[int(m.group(1))]['frequency'])

        # :SOURce[ch]:VOLTage:OFFSet?
        m = re.match(r':SOURce(\d):VOLTage:OFFSet\?', command, re.IGNORECASE)
        if m:
            return str(self._state[int(m.group(1))]['offset_v'])

        # :SOURce[ch]:VOLTage? (Amplitude)
        m = re.match(r':SOURce(\d):VOLTage\?', command, re.IGNORECASE)
        if m:
            return str(self._state[int(m.group(1))]['amplitude_vpp'])
            
        # :SOURce[ch]:FUNCtion?
        m = re.match(r':SOURce(\d):FUNCtion\?', command, re.IGNORECASE)
        if m:
            return self._state[int(m.group(1))]['function']

        # :OUTPut[ch]:STATe?
        m = re.match(r':OUTPut(\d):STATe\?', command, re.IGNORECASE)
        if m:
            return '1' if self._state[int(m.group(1))]['output_state'] == 'ON' else '0'

        # Add regex for other 'query' commands here...

        logger.error(f"Unhandled MOCK QUERY command: {command}")
        raise VisaIOError(f"Unhandled mock query: {command}")


# --- Mock ResourceManager (The 'visa' entry point) ---
class MockResourceManager:
    """
    Simulates the pyvisa.ResourceManager.
    """
    def __init__(self, *args, **kwargs):
        logger.info("MockResourceManager initialized")
        self._resources: Dict[str, MockResource] = {}

    def open_resource(self, resource_id: str, *args, **kwargs) -> MockResource:
        """
        Returns a new or existing MockResource instance.
        """
        if resource_id not in self._resources:
            self._resources[resource_id] = MockResource(resource_id)
        
        logger.info(f"MockResourceManager.open_resource({resource_id})")
        return self._resources[resource_id]

# --- Public API of the mock module ---
# These are the functions/classes the real 'pyvisa' module exposes.
ResourceManager = MockResourceManager
Resource = MockResource