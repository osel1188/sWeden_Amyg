import pyvisa as visa
import time
import logging
import os
# Assuming configurable_csv_logger.py is in the same directory or accessible in PYTHONPATH
from configurable_csv_logger import ConfigurableCsvLogger 

# Configure standard logging for the KeysightEDU class's own operational messages
# This might be configured globally in your application.
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
log = logging.getLogger(__name__) # Use a named logger

class KeysightEDU:
    """
    Represents and controls a Keysight EDU function generator,
    with command logging using ConfigurableCsvLogger.
    """
    _LOG_FILENAME_PREFIX = "keysight_edu_comms" # Define prefix for this specific logger
    _LOG_DATA_COLUMNS = ['Command', 'KeysightName', 'ResourceName'] # Define data columns

    def __init__(self, resource_name, config, name="", log_folder_path=None):
        """
        Initializes the KeysightEDU device.

        Args:
            resource_name (str): The VISA resource name (e.g., 'USB0::...').
            config (dict): Configuration dictionary for device defaults.
            name (str, optional): A user-friendly name for this instrument instance. Defaults to "".
            log_folder_path (str, optional): Path to the folder for storing CSV command logs.
                                           If None, defaults to "./log/" in the current working directory.
                                           Defaults to None.
        """
        self.name = name
        self.resource_name = resource_name
        self.config = config
        self.instrument = None
        try:
            self.rm = visa.ResourceManager()
        except Exception as e:
            log.error(f"Failed to initialize VISA ResourceManager: {e}. Please ensure a VISA backend (like NI-VISA) is installed.")
            # Depending on the application's needs, you might re-raise or handle this more gracefully.
            raise

        if log_folder_path is None:
            self.log_folder_path = os.path.join(os.getcwd(), "logs") # Default log folder
        else:
            self.log_folder_path = log_folder_path

        # Instantiate the ConfigurableCsvLogger
        self.command_logger = ConfigurableCsvLogger(
            log_folder_path=self.log_folder_path,
            filename_prefix=self._LOG_FILENAME_PREFIX,
            data_header_columns=self._LOG_DATA_COLUMNS
        )

        log.info(f"KeysightEDU object created for resource: {self.resource_name} (Name: '{self.name}')")
        log.info(f"Command logs for '{self.name}' (Resource: {self.resource_name}) will be saved as: "
                 f"'{self.command_logger.current_log_filename}' in folder: '{self.log_folder_path}'")

    def connect(self):
        """Establishes connection to the device."""
        try:
            log.info(f"Attempting to connect to {self.resource_name} (Name: '{self.name}')...")
            self.instrument = self.rm.open_resource(self.resource_name)
            self.instrument.timeout = self.config.get('timeout', 10000) # Use config or default
            self.clear() 
            identity = self.query("*IDN?") 
            log.info(f"Connected to (Name: '{self.name}'): {identity.strip() if identity else 'N/A'}")
            self.write('*RST') 
            time.sleep(self.config.get('rst_delay', 1.0)) # Use config or default
            return True
        except visa.VisaIOError as e:
            log.error(f"VISA I/O Error: Failed to connect to {self.resource_name} (Name: '{self.name}'): {e}")
            self.instrument = None
            return False
        except Exception as e:
            log.error(f"An unexpected error occurred during connection to {self.resource_name} (Name: '{self.name}'): {e}")
            self.instrument = None
            return False

    def disconnect(self):
        """Disconnects from the device and closes resources."""
        if self.instrument:
            try:
                log.info(f"Disconnecting from {self.resource_name} (Name: '{self.name}')...")
                for i in self.config.get('output_channels', [1, 2]):
                    try:
                        # Ensure set_output_state uses self.write for logging
                        self.set_output_state(i, False) 
                    except Exception: 
                        log.warning(f"Could not turn off output {i} for {self.resource_name} (Name: '{self.name}') during disconnect.")
                        pass
                time.sleep(0.1)
                self.clear() 
                self.instrument.close()
                log.info(f"Device {self.resource_name} (Name: '{self.name}') disconnected.")
            except visa.VisaIOError as e:
                log.error(f"VISA I/O Error during disconnect for {self.resource_name} (Name: '{self.name}'): {e}")
            except Exception as e:
                log.error(f"Unexpected error during disconnect for {self.resource_name} (Name: '{self.name}'): {e}")
            finally:
                self.instrument = None
        # self.rm.close() # Typically, Resource Manager is closed by the main application if it owns it.

    def write(self, command, wait_type=None, verbose=True):
        """Sends a command to the device and logs it."""
        # Log command using ConfigurableCsvLogger
        self.command_logger.log_entry(command, self.name, self.resource_name)

        if not self.instrument:
            log.warning(f"Cannot write '{command}' to {self.resource_name} (Name: '{self.name}'): Device not connected.")
            return
        try:
            if verbose:
                print(f"{self.name or self.resource_name}: {command}")
            
            self.instrument.write(command)
            
            if wait_type: # Check if wait_type is not None or empty
                wait_type_upper = wait_type.upper()
                if "OPC" in wait_type_upper:
                    self.wait_OPC() 
                elif "WAI" in wait_type_upper:
                    self.wait_WAI()
        except visa.VisaIOError as e:
            log.error(f"VISA Write Error to {self.resource_name} (Name: '{self.name}') for command ('{command}'): {e}")
            raise
        except Exception as e:
            log.error(f"Unexpected Write Error to {self.resource_name} (Name: '{self.name}') for command ('{command}'): {e}")
            raise

    def query(self, command):
        """Sends a query to the device, logs it, and returns the response."""
        # Log command using ConfigurableCsvLogger
        self.command_logger.log_entry(command, self.name, self.resource_name)

        if not self.instrument:
            log.warning(f"Cannot query '{command}' on {self.resource_name} (Name: '{self.name}'): Device not connected.")
            return None # Or raise an error
        try:
            response = self.instrument.query(command)
            return response.strip()
        except visa.VisaIOError as e:
            log.error(f"VISA Query Error to {self.resource_name} (Name: '{self.name}') for command ('{command}'): {e}")
            raise
        except Exception as e:
            log.error(f"Unexpected Query Error to {self.resource_name} (Name: '{self.name}') for command ('{command}'): {e}")
            raise

    def clear(self):
        """Clears the device status. This is a direct instrument operation, not a SCPI command log via self.write/query."""
        if self.instrument:
            try:
                self.instrument.clear()
                time.sleep(0.1) 
            except Exception as e:
                log.warning(f"Could not clear device {self.resource_name} (Name: '{self.name}'): {e}")

    def wait_OPC(self):
        """Sends *OPC? query and waits for completion. The query itself is logged by self.query."""
        try:
            self.query("*OPC?") # This query will be logged
        except Exception as e:
            log.warning(f"Error during OPC query for {self.resource_name} (Name: '{self.name}'): {e}")
            time.sleep(0.1) 

    def wait_WAI(self):
        """Sends *WAI command. The command itself is logged by self.write."""
        try:
            # verbose=False to avoid double printing if called internally, OPC/WAI are low-level
            self.write("*WAI", wait_type=None, verbose=False) 
        except Exception as e:
            log.warning(f"Error during *WAI write for {self.resource_name} (Name: '{self.name}'): {e}")
            time.sleep(0.1)

    def set_output_state(self, output_num, state):
        """Sets the state (True/False) of a specific output."""
        state_str = 'ON' if state else 'OFF'
        self.write(f':OUTPut{output_num}:STATe {state_str}')
        log.debug(f"Device {self.resource_name} (Name: '{self.name}'): Output {output_num} set to {state_str}")

    def set_voltage(self, source_num, voltage):
        """Sets the voltage amplitude for a specific source."""
        self.write(f':SOURce{source_num}:VOLTage {voltage:.4f}')

    def get_voltage(self, source_num):
        """Queries the voltage amplitude for a specific source."""
        try:
            response = self.query(f':SOURce{source_num}:VOLTage?')
            return float(response) if response is not None else 0.0
        except (ValueError, TypeError, visa.VisaIOError) as e:
            log.error(f"Error getting voltage for Source {source_num} on {self.resource_name} (Name: '{self.name}'): {e}")
            return 0.0
        except Exception as e:
            log.error(f"Unexpected error getting voltage for Source {source_num} on {self.resource_name} (Name: '{self.name}'): {e}")
            return 0.0

    def apply_sinusoid(self, source_num, frequency, voltage, offset=0, phase=0):
        """Configures the source to output a sinusoid with optional offset and phase."""
        # Format: :SOURce<n>:APPLy:SINusoid [<frequency>[, <amplitude>[, <offset>[, <phase>]]]]
        self.write(f':SOURce{source_num}:APPLy:SINusoid {frequency},{voltage:.4f},{offset:.4f},{phase}')

    def setup_defaults(self, defaults_config):
        """Applies default settings from the configuration."""
        log.info(f"Setting up defaults for {self.resource_name} (Name: '{self.name}')...")
        load = defaults_config.get('load_impedance', 'INFinity')
        func = defaults_config.get('function', 'SIN')
        burst_cycles = defaults_config.get('burst_num_cycles', 'INFinity')
        burst_state = defaults_config.get('burst_state', True)
        burst_mode = defaults_config.get('burst_mode', 'TRIGgered')
        burst_phase = defaults_config.get('burst_phase', 0)
        
        #self.write('*RST') # Start fresh
        for i in self.config.get('source_channels', [1, 2]):
            out_num = i # Assuming output number matches source number for these commands
            # Ensure output is off before changing settings
            self.set_output_state(out_num, False)
            time.sleep(0.05)
            
            self.write(f':OUTPut{out_num}:LOAD {load}')
            self.write(f':SOURce{i}:FUNCtion {func}')
            self.write(f':SOURce{i}:BURSt:NCYCles {burst_cycles}')
            self.write(f':SOURce{i}:BURSt:STATe {1 if burst_state else 0}')
            self.write(f':SOURce{i}:BURSt:MODE {burst_mode}')
            self.write(f':SOURce{i}:BURSt:PHASe {burst_phase}')
            log.debug(f"Device {self.resource_name} (Name: '{self.name}'): Source {i} defaults applied.")
            # self.write(':SOURce%d:VOLTage:COUPle:STATe %d' % (i, 1)) # Is coupling needed? Check device manual
    
    def configure_trigger(self, source_num, trigger_source='BUS', delay=0):
        """Configures the trigger source and optional delay for a specific source channel."""
        # Trigger sources: IMMediate, EXTernal, BUS, TIMer
        self.write(f':TRIGger{source_num}:SOURce {trigger_source}')
        if trigger_source.upper() == 'TIMER':
            # If timer, you might need to set :TRIGger<n>:TIMer <time>
            log.warning(f"Trigger source for CH{source_num} set to TIMER. Ensure :TRIGger{source_num}:TIMer is set if needed.")
        self.write(f':TRIGger{source_num}:DELay {delay}') # Delay in seconds
        log.debug(f"Device {self.resource_name} (Name: '{self.name}'): Source {source_num} trigger set to {trigger_source} with delay {delay}s")

    def configure_output_trigger(self, output_num=1, state=False, source='CH1'):
        """ 
        Enables or disables the output trigger signal (TRIG OUT).
        Typically, only one output trigger exists, often associated with Output 1 or a master trigger.
        Args:
            output_num (int): Usually 1 for the main trigger output. Check device manual.
            state (bool): True to enable output trigger, False to disable.
            source (str): Source for the trigger output signal (e.g., 'CH1', 'CH2', 'MANual').
                          'MANual' might mean it triggers when *TRG is sent.
        """
        # The command might vary slightly; common is :OUTPut:TRIGger[:STATe] and :OUTPut:TRIGger:SOURce
        # For EDU3321xA series, it's often :OUTPut:TRIGger:SOURce CH1|CH2|MANual
        # And :OUTPut:TRIGger[:STATe] ON|OFF (or :OUTPut:TRIGger ON|OFF for some)
        # We'll assume output_num is for devices with multiple distinct trigger outputs,
        # but for EDU series, it's usually one main trigger out.
        
        self.write(f':OUTPut:TRIGger:SOURce {source}') # Sets what event generates the trigger out pulse
        self.write(f':OUTPut:TRIGger {1 if state else 0}') # Enables/disables the Trig Out connector
        log.debug(f"Device {self.resource_name} (Name: '{self.name}'): Output Trigger (connector) state set to {state}, source {source}")


    def trigger(self):
        """Sends a software trigger (*TRG)."""
        log.info(f"Device {self.resource_name} (Name: '{self.name}'): Software trigger sent.")
        self.write('*TRG')

    def abort(self):
        """Aborts operations. For EDU series, this stops the current waveform generation."""
        self.write(':ABORt') # Or :SOURce[1|2]:ABORt for some specific models if needed
        log.info(f"Device {self.resource_name} (Name: '{self.name}'): Abort command sent.")

    def beep(self):
        """Triggers the system beeper."""
        try:
            self.write('SYSTem:BEEPer:IMMediate')
        except Exception as e:
            log.warning(f"Could not trigger beep on {self.resource_name} (Name: '{self.name}'): {e}")

    def __del__(self):
        # Ensure disconnection when the object is destroyed, although explicit disconnect is preferred.
        # This might not run reliably in all Python exit scenarios.
        # self.disconnect() # Consider if this is safe or if it should be explicitly managed.
        log.debug(f"KeysightEDU object for {self.resource_name} (Name: '{self.name}') is being deleted.")
        # If self.rm was created here and not passed in, consider self.rm.close()
        # However, pyvisa often manages this globally or it's closed by the app.
