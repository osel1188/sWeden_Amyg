import time
import logging
import random
import re # For parsing commands
import os


# Assuming configurable_csv_logger.py is in the same directory or accessible in PYTHONPATH
from configurable_csv_logger import ConfigurableCsvLogger 

# Configure standard logging (for general operational messages, not command logging)
# This should ideally be configured once in your main application script.
# If not configured elsewhere, this basicConfig will apply.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')

# Use a named logger for the mockup class itself (distinct from command log file)
log = logging.getLogger(__name__) # Gets a logger named after the current module

# REMOVED: ConfigurableCsvLogger class definition was here. It's now imported.

class KeysightEDUMockup:
    """
    A mockup-up of the KeysightEDU class for testing without hardware.
    Simulates device responses and state changes, logs actions to console and CSV
    using ConfigurableCsvLogger.
    """
    _LOG_FILENAME_PREFIX = "keysight_mockup_comms" # Define prefix for this specific logger
    _LOG_DATA_COLUMNS = ['Command', 'KeysightName', 'ResourceName'] # Define data columns

    def __init__(self, resource_name, config, name="", log_folder_path=None):
        """
        Initializes the KeysightEDUMockup device.

        Args:
            resource_name (str): The simulated VISA resource name.
            config (dict): Configuration dictionary (used for channels).
            name (str, optional): A user-friendly name for this instrument instance. Defaults to "".
            log_folder_path (str, optional): Path to the folder for storing CSV command logs.
                                           If None, defaults to "./log/" in the current working directory.
                                           Defaults to None.
        """
        self.name = name
        self.resource_name = resource_name
        self.config = config
        self.instrument = None
        self.mockup_identity = f"Mockup Keysight EDU, S/N {random.randint(1000, 9999)}, FW 1.0 @ {self.resource_name}"

        self.voltages = {}
        self.output_states = {}
        self.trigger_source = {}
        self.output_trigger_state = {}
        self.is_connected = False
        self.is_aborted = True

        for i in self.config.get('source_channels', [1, 2]):
            self.voltages[i] = 0.0
            self.trigger_source[i] = 'IMMediate'
        for i in self.config.get('output_channels', [1, 2]):
            self.output_states[i] = False
            self.output_trigger_state[i] = False

        if log_folder_path is None:
            self.log_folder_path = os.path.join(os.getcwd(), "logs")
        else:
            self.log_folder_path = log_folder_path
        
        # Instantiate the imported ConfigurableCsvLogger
        self.command_logger = ConfigurableCsvLogger(
            log_folder_path=self.log_folder_path,
            filename_prefix=self._LOG_FILENAME_PREFIX,
            data_header_columns=self._LOG_DATA_COLUMNS
        )

        log.info(f"MOCK KeysightEDU object created for resource: {self.resource_name} (Name: '{self.name}')")
        log.info(f"MOCK Command logs for '{self.name}' will be saved as: '{self.command_logger.current_log_filename}' in folder: '{self.log_folder_path}'")


    def connect(self):
        if self.is_connected:
            log.warning(f"MOCK {self.resource_name} (Name: '{self.name}'): Already connected.")
            return True
        log.info(f"MOCK Connecting to {self.resource_name} (Name: '{self.name}')...")
        time.sleep(random.uniform(0.1, 0.3))
        self.instrument = True
        self.is_connected = True
        self.is_aborted = True
        
        self.query("*IDN?")
        self.write("*RST")
        
        log.info(f"MOCK Connected to (Name: '{self.name}'): {self.mockup_identity}")
        return True

    def disconnect(self):
        if not self.is_connected:
            log.warning(f"MOCK {self.resource_name} (Name: '{self.name}'): Already disconnected.")
            return

        log.info(f"MOCK Disconnecting from {self.resource_name} (Name: '{self.name}')...")
        for i in self.config.get('output_channels', [1, 2]):
            if self.output_states.get(i, False):
                log.debug(f"MOCK {self.resource_name} (Name: '{self.name}'): Simulating turning Output {i} OFF on disconnect.")
                self.set_output_state(i, False)

        time.sleep(random.uniform(0.05, 0.1))
        self.instrument = None
        self.is_connected = False
        log.info(f"MOCK Device {self.resource_name} (Name: '{self.name}') disconnected.")

    def write(self, command, verbose=True):
        # Use the logger's log_entry method
        self.command_logger.log_entry(command, self.name, self.resource_name)

        log.debug(f"MOCK WRITE to {self.resource_name} (Name: '{self.name}'): {command}")
        if verbose:
            print(f"MOCK {self.name or self.resource_name}: {command}")

        if not self.is_connected:
            log.error(f"MOCK {self.resource_name} (Name: '{self.name}'): Cannot write '{command}', device not connected.")
            return

        command_upper = command.upper()
        # (Rest of the command parsing logic from the original mockup remains the same)
        match = re.match(r':OUTP(?:UT)?(\d+):STAT(?:E)?\s+(ON|OFF|1|0)', command_upper)
        if match:
            ch = int(match.group(1))
            state = match.group(2) in ['ON', '1']
            log.info(f"MOCK {self.resource_name} (Name: '{self.name}'): Setting Output {ch} state to {state}")
            self.output_states[ch] = state
            self.is_aborted = False
            return

        match = re.match(r':SOUR(?:CE)?(\d+):VOLT(?:AGE)?\s+([+-]?\d+(?:\.\d*)?)', command_upper)
        if match:
            src = int(match.group(1))
            volt = float(match.group(2))
            log.info(f"MOCK {self.resource_name} (Name: '{self.name}'): Setting Source {src} voltage to {volt:.4f}")
            self.voltages[src] = volt
            return

        match = re.match(r':SOUR(?:CE)?(\d+):APPL(?:Y)?:SIN(?:USOID)?\s+([\dE.]+)\s*,\s*([+-]?\d+(?:\.\d*)?)', command_upper, re.IGNORECASE)
        if match:
            src = int(match.group(1))
            freq_str = match.group(2)
            volt_str = match.group(3)
            try:
                freq = float(freq_str)
                volt = float(volt_str)
                log.info(f"MOCK {self.resource_name} (Name: '{self.name}'): Applying Sinusoid to Source {src} (Freq: {freq}, Volt: {volt:.4f})")
                self.voltages[src] = volt
            except ValueError:
                log.error(f"MOCK {self.resource_name} (Name: '{self.name}'): Could not parse freq/volt for APPLY:SIN: {freq_str}, {volt_str}")
            return
            
        if '*RST' in command_upper:
            log.info(f"MOCK {self.resource_name} (Name: '{self.name}'): Received *RST. Resetting mock state.")
            for i_key in self.config.get('source_channels', [1, 2]):
                self.voltages[i_key] = 0.0
                self.trigger_source[i_key] = 'IMMediate'
            for i_key in self.config.get('output_channels', [1, 2]):
                self.output_states[i_key] = False
                self.output_trigger_state[i_key] = False
            self.is_aborted = True
            return

        if ':ABOR' in command_upper:
            log.info(f"MOCK {self.resource_name} (Name: '{self.name}'): Aborting operations.")
            self.is_aborted = True
            return

        if '*TRG' in command_upper:
            log.info(f"MOCK {self.resource_name} (Name: '{self.name}'): Software trigger (*TRG) received.")
            self.is_aborted = False
            return

        if 'SYST:BEEP' in command_upper:
            log.info(f"MOCK {self.resource_name} (Name: '{self.name}'): Beep!")
            return

        match = re.match(r':TRIG(?:GER)?(\d+):SOUR(?:CE)?\s+(\w+)', command_upper)
        if match:
            src = int(match.group(1))
            trg_src = match.group(2)
            log.info(f"MOCK {self.resource_name} (Name: '{self.name}'): Setting Trigger {src} source to {trg_src}")
            self.trigger_source[src] = trg_src
            return

        match = re.match(r':OUTP(?:UT)?(\d+):TRIG(?:GER)?:STAT(?:E)?\s+(1|0|ON|OFF)', command_upper)
        if match:
            out_num = int(match.group(1))
            state = match.group(2) in ['1', 'ON']
            log.info(f"MOCK {self.resource_name} (Name: '{self.name}'): Setting Output {out_num} Trigger State to {state}")
            self.output_trigger_state[out_num] = state
            return


    def query(self, command):
        # Use the logger's log_entry method
        self.command_logger.log_entry(command, self.name, self.resource_name)
        
        log.debug(f"MOCK QUERY to {self.resource_name} (Name: '{self.name}'): {command}")

        if not self.is_connected:
            log.error(f"MOCK {self.resource_name} (Name: '{self.name}'): Cannot query '{command}', device not connected.")
            return "MOCK_ERROR_NOT_CONNECTED"

        time.sleep(random.uniform(0.01, 0.05))
        command_upper = command.upper().strip()
        response = "MOCK_UNKNOWN_QUERY"

        if command_upper == "*IDN?":
            response = self.mockup_identity
        elif command_upper == "*OPC?":
            response = "1"
        elif ':SOUR' in command_upper and ':VOLT' in command_upper and '?' in command_upper:
            match_volt_query = re.search(r':SOUR(?:CE)?(\d+):VOLT(?:AGE)?\?', command_upper)
            if match_volt_query:
                src = int(match_volt_query.group(1))
                response = f"{self.voltages.get(src, 0.0):.5E}"
            else:
                response = "+0.00000E+00"
        elif ':OUTP' in command_upper and ':STAT' in command_upper and '?' in command_upper:
            match_out_stat_query = re.search(r':OUTP(?:UT)?(\d+):STAT(?:E)?\?', command_upper)
            if match_out_stat_query:
                ch = int(match_out_stat_query.group(1))
                response = str(1 if self.output_states.get(ch, False) else 0)
            else:
                response = "0"
        
        log.debug(f"MOCK RESPONSE from {self.resource_name} (Name: '{self.name}'): {response}")
        return response

    def clear(self):
        if not self.is_connected:
            log.warning(f"MOCK {self.resource_name} (Name: '{self.name}'): Clear called but not connected.")
            return
        log.info(f"MOCK {self.resource_name} (Name: '{self.name}'): Status cleared.")
        time.sleep(0.02)

    def wait_OPC(self):
        log.debug(f"MOCK {self.resource_name} (Name: '{self.name}'): wait_OPC called (Simulating via *OPC?).")
        self.query("*OPC?")

    def wait_WAI(self):
        log.debug(f"MOCK {self.resource_name} (Name: '{self.name}'): wait_WAI called (Simulating *WAI).")
        self.write("*WAI", verbose=False)

    def set_output_state(self, output_num, state):
        self.write(f':OUTPut{output_num}:STATe {"ON" if state else "OFF"}')

    def set_voltage(self, source_num, voltage):
        self.write(f':SOURce{source_num}:VOLTage {voltage:.4f}')

    def get_voltage(self, source_num):
        response = self.query(f':SOURce{source_num}:VOLTage?')
        try:
            return float(response)
        except ValueError:
            log.error(f"MOCK {self.resource_name} (Name: '{self.name}'): Failed to parse mockup voltage response '{response}'")
            return 0.0

    def apply_sinusoid(self, source_num, frequency, voltage):
        self.write(f':SOURce{source_num}:APPLy:SINusoid {frequency},{voltage:.4f}')

    def setup_defaults(self, defaults_config):
        log.info(f"MOCK {self.resource_name} (Name: '{self.name}'): Applying default setup (simulated).")
        load = defaults_config.get('load_impedance', 'INFinity')
        func = defaults_config.get('function', 'SIN')
        burst_cycles = defaults_config.get('burst_num_cycles', 'INFinity')
        burst_state = defaults_config.get('burst_state', True)
        burst_mode = defaults_config.get('burst_mode', 'TRIGgered')
        burst_phase = defaults_config.get('burst_phase', 0)

        for i in self.config.get('source_channels', [1, 2]):
            out_num = i
            self.set_output_state(out_num, False)
            time.sleep(0.01)
            self.write(f':OUTPut{out_num}:LOAD {load}')
            self.write(f':SOURce{i}:FUNCtion {func}')
            self.write(f':SOURce{i}:BURSt:NCYCles {burst_cycles}')
            self.write(f':SOURce{i}:BURSt:STATe {1 if burst_state else 0}')
            self.write(f':SOURce{i}:BURSt:MODE {burst_mode}')
            self.write(f':SOURce{i}:BURSt:PHASe {burst_phase}')
        log.debug(f"MOCK {self.resource_name} (Name: '{self.name}'): Default commands simulated.")

    def configure_trigger(self, source_num, trigger_source):
        self.write(f':TRIGger{source_num}:SOURce {trigger_source}')

    def configure_output_trigger(self, output_num, state):
        self.write(f':OUTPut{output_num}:TRIGger:STATe {"ON" if state else "OFF"}')

    def trigger(self):
        self.write('*TRG')

    def abort(self):
        self.write(':ABORt')

    def beep(self):
        self.write('SYSTem:BEEPer:IMMediate')

    def __del__(self):
        log.debug(f"MOCK KeysightEDU object for {self.resource_name} (Name: '{self.name}') is being destroyed.")



# Example Usage (Illustrative)
if __name__ == "__main__":
    # Create a dummy configurable_csv_logger.py for this example to run standalone
    # In a real scenario, this file would exist separately.
    if not os.path.exists("configurable_csv_logger.py"):
        with open("configurable_csv_logger.py", "w") as f:
            f.write("import csv\n")
            f.write("import os\n")
            f.write("from datetime import datetime\n")
            f.write("import logging\n")
            f.write("class ConfigurableCsvLogger:\n")
            f.write("    def __init__(self, log_folder_path: str, filename_prefix: str, data_header_columns: list[str]):\n")
            f.write("        self.log_folder_path = log_folder_path\n")
            f.write("        self.filename_prefix = filename_prefix\n")
            f.write("        self.user_defined_header_columns = data_header_columns\n")
            f.write("        self.full_header = ['Timestamp'] + self.user_defined_header_columns\n")
            f.write("        os.makedirs(self.log_folder_path, exist_ok=True)\n")
            f.write("        creation_timestamp_str = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')\n")
            f.write("        self.current_log_filename = f\"{creation_timestamp_str}_{self.filename_prefix}.csv\"\n")
            f.write("        self.log_file_path = os.path.join(self.log_folder_path, self.current_log_filename)\n")
            f.write("        try:\n")
            f.write("            with open(self.log_file_path, 'w', newline='') as csvfile:\n")
            f.write("                writer = csv.writer(csvfile)\n")
            f.write("                writer.writerow(self.full_header)\n")
            f.write("            logging.info(f\"Log file created: {self.log_file_path} with header: {self.full_header}\")\n")
            f.write("        except IOError as e:\n")
            f.write("            logging.error(f\"Failed to create or write header to log file {self.log_file_path}: {e}\")\n")
            f.write("            raise\n")
            f.write("    def _get_formatted_timestamp(self) -> str:\n")
            f.write("        return datetime.now().strftime('%Y-%m-%d_%H-%M-%S-%f')[:-3]\n")
            f.write("    def log_entry(self, *data_values: any):\n")
            f.write("        if len(data_values) != len(self.user_defined_header_columns):\n")
            f.write("            logging.error(f\"Data logging error: Expected {len(self.user_defined_header_columns)} values, got {len(data_values)}\")\n")
            f.write("            return\n")
            f.write("        timestamp = self._get_formatted_timestamp()\n")
            f.write("        log_row_data = [timestamp] + list(data_values)\n")
            f.write("        try:\n")
            f.write("            with open(self.log_file_path, 'a', newline='') as csvfile:\n")
            f.write("                writer = csv.writer(csvfile)\n")
            f.write("                writer.writerow(log_row_data)\n")
            f.write("        except IOError as e:\n")
            f.write("            logging.error(f\"Failed to write to log file {self.log_file_path}: {e}\")\n")
            f.write("        except Exception as ex:\n")
            f.write("            logging.error(f\"An unexpected error occurred: {ex}\")\n")
        # Re-import after creating the dummy file for the __main__ block
        from configurable_csv_logger import ConfigurableCsvLogger


    log.info("--- Starting Mockup Test ---")

    mock_config = {
        'source_channels': [1, 2],
        'output_channels': [1, 2],
        'defaults': {
            'load_impedance': 'INFinity',
            'function': 'SQUare',
            'burst_num_cycles': 10,
            'burst_state': True,
            'burst_mode': 'GATed',
            'burst_phase': 90
        }
    }

    mock_device1 = KeysightEDUMockup(
        resource_name="GPIB0::10::INSTR_MOCK1",
        config=mock_config,
        name="FG_Mock_DefaultLog"
    )
    if mock_device1.connect():
        mock_device1.setup_defaults(mock_config['defaults'])
        mock_device1.set_voltage(1, 1.23)
        mock_device1.set_output_state(1, True)
        v1 = mock_device1.get_voltage(1)
        log.info(f"Mock device 1, Source 1 voltage read: {v1}")
        mock_device1.trigger()
        mock_device1.disconnect()

    log.info("--- Mockup Test 1 Finished ---")
    
    custom_log_dir = "./my_mock_logs"
    log.info(f"Custom log directory for next test: {os.path.abspath(custom_log_dir)}")
    mock_device2 = KeysightEDUMockup(
        resource_name="USB0::MOCK2::INSTR",
        config={'source_channels': [1], 'output_channels': [1]},
        name="FG_Mock_CustomLog",
        log_folder_path=custom_log_dir
    )
    if mock_device2.connect():
        mock_device2.apply_sinusoid(1, 1000, 2.5) # Freq: 1000 Hz, Volt: 2.5 V
        mock_device2.set_output_state(1, True)
        mock_device2.beep()
        mock_device2.disconnect()

    log.info("--- Mockup Test 2 Finished ---")

    # Clean up the dummy file if it was created
    if os.path.exists("configurable_csv_logger.py") and "class ConfigurableCsvLogger" in open("configurable_csv_logger.py").read():
        # A bit of a heuristic to check if it's our dummy file
        try:
            os.remove("configurable_csv_logger.py")
            # Also try to remove __pycache__ if it was created for the dummy module
            if os.path.exists("__pycache__"):
                import shutil
                shutil.rmtree("__pycache__")
            log.info("Cleaned up dummy configurable_csv_logger.py and __pycache__")
        except Exception as e:
            log.warning(f"Could not clean up dummy files: {e}")

