# mockup_keysight_edu.py
import time
import logging
import random
import re # For parsing commands

# Configure logging (can be same as main app or specific)
# Ensure logging is configured in your main script or controller
log = logging.getLogger(__name__) # Use a named logger

class KeysightEDUMockup:
    """
    A mockup-up of the KeysightEDU class for testing without hardware.
    Simulates device responses and state changes, logs actions.
    """
    def __init__(self, resource_name, config):
        """
        Initializes the KeysightEDUMockup device.

        Args:
            resource_name (str): The simulated VISA resource name.
            config (dict): Configuration dictionary (used for channels).
        """
        self.resource_name = resource_name
        self.config = config # Store config for channel info etc.
        self.instrument = None # Represents the connection state conceptually
        self.mockup_identity = f"Mockup Keysight EDU, S/N {random.randint(1000, 9999)}, FW 1.0 @ {self.resource_name}"

        # Internal state simulation
        self.voltages = {} # {source_num: voltage} e.g. {1: 0.0, 2: 0.0}
        self.output_states = {} # {output_num: state} e.g. {1: False, 2: False}
        self.trigger_source = {} # {source_num: trigger_src} e.g. {1: 'BUS'}
        self.output_trigger_state = {} # {output_num: state} e.g. {1: False}
        self.is_connected = False
        self.is_aborted = True # Start in aborted state

        # Initialize state based on config channels
        for i in self.config.get('source_channels', [1, 2]):
            self.voltages[i] = 0.0
            self.trigger_source[i] = 'IMMediate' # Default state
        for i in self.config.get('output_channels', [1, 2]):
            self.output_states[i] = False
            self.output_trigger_state[i] = False


        log.info(f"MOCK KeysightEDU object created for resource: {self.resource_name}")

    def connect(self):
        """Simulates establishing connection to the device."""
        if self.is_connected:
            log.warning(f"MOCK {self.resource_name}: Already connected.")
            return True
        log.info(f"MOCK Connecting to {self.resource_name}...")
        time.sleep(random.uniform(0.1, 0.3)) # Simulate connection time
        self.instrument = True # Simulate successful connection handle
        self.is_connected = True
        self.is_aborted = True # Reset aborted state on connect
        log.info(f"MOCK Connected to: {self.mockup_identity}")
        return True

    def disconnect(self):
        """Simulates disconnecting from the device."""
        if not self.is_connected:
            log.warning(f"MOCK {self.resource_name}: Already disconnected.")
            return

        log.info(f"MOCK Disconnecting from {self.resource_name}...")
        # Simulate turning off outputs on disconnect
        for i in self.config.get('output_channels', [1, 2]):
             if self.output_states.get(i, False):
                 log.debug(f"MOCK {self.resource_name}: Simulating turning Output {i} OFF on disconnect.")
                 self.output_states[i] = False
        time.sleep(random.uniform(0.05, 0.1))
        self.instrument = None
        self.is_connected = False
        log.info(f"MOCK Device {self.resource_name} disconnected.")

    def write(self, command):
        """Simulates sending a command to the device."""
        log.debug(f"MOCK WRITE to {self.resource_name}: {command}")
        if not self.is_connected:
            log.error(f"MOCK {self.resource_name}: Cannot write '{command}', device not connected.")
            # raise ConnectionError(f"Mockup device {self.resource_name} not connected")
            return # Silently fail or raise error depending on desired strictness

        # --- Simulate Effects of Common Commands ---
        # Simple parser for common commands to update internal state
        command_upper = command.upper()

        # Output State
        match = re.match(r':OUTP(?:UT)?(\d+):STAT(?:E)?\s+(ON|OFF|1|0)', command_upper)
        if match:
            ch = int(match.group(1))
            state = match.group(2) in ['ON', '1']
            log.info(f"MOCK {self.resource_name}: Setting Output {ch} state to {state}")
            self.output_states[ch] = state
            self.is_aborted = False # Assume output on means not aborted
            return

        # Voltage Set
        match = re.match(r':SOUR(?:CE)?(\d+):VOLT(?:AGE)?\s+([+-]?\d+(?:\.\d*)?)', command_upper)
        if match:
            src = int(match.group(1))
            volt = float(match.group(2))
            log.info(f"MOCK {self.resource_name}: Setting Source {src} voltage to {volt:.4f}")
            self.voltages[src] = volt
            return

        # Apply Sinusoid (includes voltage)
        match = re.match(r':SOUR(?:CE)?(\d+):APPL(?:Y)?:SIN(?:USOID)?\s+([\d.]+)\s*,\s*([+-]?\d+(?:\.\d*)?)', command_upper)
        if match:
            src = int(match.group(1))
            freq = float(match.group(2))
            volt = float(match.group(3))
            log.info(f"MOCK {self.resource_name}: Applying Sinusoid to Source {src} (Freq: {freq}, Volt: {volt:.4f})")
            self.voltages[src] = volt
            # Could store frequency too if needed
            return

        # Abort
        if ':ABOR' in command_upper:
            log.info(f"MOCK {self.resource_name}: Aborting operations.")
            self.is_aborted = True
            # Simulate outputs potentially turning off on abort? Depends on device
            # for ch in self.output_states: self.output_states[ch] = False
            return

        # Trigger
        if '*TRG' in command_upper:
             log.info(f"MOCK {self.resource_name}: Software trigger (*TRG) received.")
             self.is_aborted = False # Trigger implies starting something
             return

        # Beep
        if 'SYST:BEEP' in command_upper:
            log.info(f"MOCK {self.resource_name}: Beep!")
            return

        # Trigger Source Config
        match = re.match(r':TRIG(?:GER)?(\d+):SOUR(?:CE)?\s+(\w+)', command_upper)
        if match:
            src = int(match.group(1))
            trg_src = match.group(2)
            log.info(f"MOCK {self.resource_name}: Setting Trigger {src} source to {trg_src}")
            self.trigger_source[src] = trg_src
            return

        # Output Trigger State Config
        match = re.match(r':OUTP(?:UT)?(\d+):TRIG(?:GER)?:STAT(?:E)?\s+(1|0|ON|OFF)', command_upper)
        if match:
            out_num = int(match.group(1))
            state = match.group(2) in ['1', 'ON']
            log.info(f"MOCK {self.resource_name}: Setting Output {out_num} Trigger State to {state}")
            self.output_trigger_state[out_num] = state
            return

        # Catch-all for other commands (just log)
        # log.debug(f"MOCK {self.resource_name}: Received unparsed write command: {command}")


    def query(self, command):
        """Simulates sending a query and receiving a response."""
        log.debug(f"MOCK QUERY to {self.resource_name}: {command}")
        if not self.is_connected:
            log.error(f"MOCK {self.resource_name}: Cannot query '{command}', device not connected.")
            # raise ConnectionError(f"Mockup device {self.resource_name} not connected")
            return "MOCK_ERROR_NOT_CONNECTED" # Return dummy error string

        time.sleep(random.uniform(0.01, 0.05)) # Simulate query time

        # --- Simulate Responses to Common Queries ---
        command_upper = command.upper().strip()

        if command_upper == "*IDN?":
            response = self.mockup_identity
        elif command_upper == "*OPC?":
            # Operation Complete Query: Essential for sync. Assume immediate completion.
            response = "1"
        elif ':SOUR' in command_upper and ':VOLT' in command_upper and '?' in command_upper:
            match = re.search(r':SOUR(?:CE)?(\d+):VOLT(?:AGE)?\?', command_upper)
            if match:
                 src = int(match.group(1))
                 response = f"{self.voltages.get(src, 0.0):.5E}" # Scientific notation often used
                 log.debug(f"MOCK {self.resource_name}: Responding to voltage query for Source {src} with {response}")
            else:
                 response = "+0.00000E+00" # Default voltage response
                 log.warning(f"MOCK {self.resource_name}: Could not parse voltage query: {command}")
        elif ':OUTP' in command_upper and ':STAT' in command_upper and '?' in command_upper:
             match = re.search(r':OUTP(?:UT)?(\d+):STAT(?:E)?\?', command_upper)
             if match:
                 ch = int(match.group(1))
                 state_val = 1 if self.output_states.get(ch, False) else 0
                 response = str(state_val)
                 log.debug(f"MOCK {self.resource_name}: Responding to output state query for Ch {ch} with {response}")
             else:
                 response = "0"
                 log.warning(f"MOCK {self.resource_name}: Could not parse output state query: {command}")
        else:
            # Default response for unknown queries
            response = "MOCK_UNKNOWN_QUERY"
            log.warning(f"MOCK {self.resource_name}: Received unknown query: {command}. Sending default response.")

        log.debug(f"MOCK RESPONSE from {self.resource_name}: {response}")
        return response

    def clear(self):
        """Simulates clearing the device status."""
        if not self.is_connected:
             log.warning(f"MOCK {self.resource_name}: Clear called but not connected.")
             return
        log.info(f"MOCK {self.resource_name}: Status cleared.")
        time.sleep(0.02)

    def wait(self):
        """Simulates waiting for operation complete (e.g., *OPC?)."""
        # In the mockup, query("*OPC?") achieves this simulation
        log.debug(f"MOCK {self.resource_name}: Wait called (Simulating via *OPC?).")
        self.query("*OPC?") # Log the query and return "1"

    # --- Direct Action Methods (mirroring KeysightEDU) ---

    def set_output_state(self, output_num, state):
        """Simulates setting the state (True/False) of a specific output."""
        state_cmd = 'ON' if state else 'OFF'
        self.write(f':OUTPut{output_num}:STATe {state_cmd}')

    def set_voltage(self, source_num, voltage):
        """Simulates setting the voltage amplitude for a specific source."""
        self.write(f':SOURce{source_num}:VOLTage {voltage:.4f}')

    def get_voltage(self, source_num):
        """Simulates querying the voltage amplitude for a specific source."""
        response = self.query(f':SOURce{source_num}:VOLTage?')
        try:
            return float(response)
        except ValueError:
            log.error(f"MOCK {self.resource_name}: Failed to parse mockup voltage response '{response}'")
            return 0.0 # Return default on error

    def apply_sinusoid(self, source_num, frequency, voltage):
        """Simulates configuring the source to output a sinusoid."""
        self.write(f':SOURce{source_num}:APPLy:SINusoid {frequency},{voltage:.4f}')

    def setup_defaults(self, defaults_config):
        """Simulates applying default settings."""
        log.info(f"MOCK {self.resource_name}: Applying default setup (simulated).")
        # Simulate writing the commands based on defaults_config keys
        load = defaults_config.get('load_impedance', 'INFinity')
        func = defaults_config.get('function', 'SIN')
        # ... add writes for burst, phase etc. using self.write() ...
        for i in self.config.get('source_channels', [1, 2]):
            out_num = i
            # Ensure output off command is sent
            self.write(f':OUTPut{out_num}:STATe OFF')
            time.sleep(0.01)
            self.write(f':OUTPut{out_num}:LOAD {load}')
            self.write(f':SOURce{i}:FUNCtion {func}')
            # ... add other default commands here
        log.debug(f"MOCK {self.resource_name}: Default commands simulated.")


    def configure_trigger(self, source_num, trigger_source):
        """Simulates configuring the trigger source."""
        self.write(f':TRIGger{source_num}:SOURce {trigger_source}')

    def configure_output_trigger(self, output_num, state):
         """Simulates configuring the output trigger state."""
         state_str = 'ON' if state else 'OFF'
         self.write(f':OUTPut{output_num}:TRIGger:STATe {state_str}')

    def trigger(self):
        """Simulates sending a software trigger (*TRG)."""
        self.write('*TRG')

    def abort(self):
        """Simulates aborting operations."""
        self.write(':ABORt')

    def beep(self):
        """Simulates triggering the system beeper."""
        self.write('SYSTem:BEEPer:IMMediate')

    def __del__(self):
        # Optional: Log object destruction
        log.debug(f"MOCK KeysightEDU object for {self.resource_name} is being destroyed.")
        # Ensure disconnect isn't called automatically if relying on explicit calls