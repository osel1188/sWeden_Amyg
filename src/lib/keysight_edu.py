# keysight_edu.py
import pyvisa as visa
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class KeysightEDU:
    """
    Represents and controls a Keysight EDU function generator.
    """
    def __init__(self, resource_name, config,  name=""):
        """
        Initializes the KeysightEDU device.

        Args:
            resource_name (str): The VISA resource name (e.g., 'USB0::...')
            config (dict): Configuration dictionary for device defaults.
        """
        self.name = name
        self.resource_name = resource_name
        self.config = config
        self.instrument = None
        self.rm = visa.ResourceManager()
        self.write('*RST') # Start fresh
        time.sleep(1.00)
        logging.info(f"KeysightEDU object created for resource: {self.resource_name}")

    def connect(self):
        """Establishes connection to the device."""
        try:
            logging.info(f"Attempting to connect to {self.resource_name}...")
            self.instrument = self.rm.open_resource(self.resource_name)
            self.instrument.timeout = 10000 # Set timeout (e.g., 10 seconds)
            self.clear()
            identity = self.query("*IDN?")
            logging.info(f"Connected to: {identity.strip()}")
            return True
        except visa.VisaIOError as e:
            logging.error(f"Failed to connect to {self.resource_name}: {e}")
            self.instrument = None
            return False
        except Exception as e:
            logging.error(f"An unexpected error occurred during connection to {self.resource_name}: {e}")
            self.instrument = None
            return False

    def disconnect(self):
        """Disconnects from the device and closes resources."""
        if self.instrument:
            try:
                logging.info(f"Disconnecting from {self.resource_name}...")
                # Turn off outputs before closing for safety
                for i in self.config.get('output_channels', [1, 2]):
                     try:
                        self.set_output_state(i, False)
                     except Exception: # Ignore errors if device is already unresponsive
                        pass
                time.sleep(0.1)
                self.clear()
                self.instrument.close()
                logging.info(f"Device {self.resource_name} disconnected.")
            except visa.VisaIOError as e:
                logging.error(f"Error during disconnect for {self.resource_name}: {e}")
            except Exception as e:
                logging.error(f"Unexpected error during disconnect for {self.resource_name}: {e}")
            finally:
                self.instrument = None
        # Don't close the resource manager here if other devices might use it.
        # It will be closed by the controller that owns it.

    def write(self, command, wait_type = None, verbose=True):
        """Sends a command to the device."""
        if not self.instrument:
            logging.warning(f"Cannot write '{command}': Device {self.resource_name} not connected.")
            return
        try:
            if verbose: print(f"{self.name}: {command}")

            # logging.debug(f"WRITE to {self.resource_name}: {command}")
            self.instrument.write(command)
            if wait_type is None:
                pass
            elif "OPC" in wait_type:
                self.wait_OPC() # Ensure command completion
            elif "WAI" in wait_type:
                self.wait_WAI()
        except visa.VisaIOError as e:
            logging.error(f"VISA Write Error to {self.resource_name} ('{command}'): {e}")
            # Consider attempting reconnect or raising exception
            raise
        except Exception as e:
            logging.error(f"Unexpected Write Error to {self.resource_name} ('{command}'): {e}")
            raise

    def query(self, command):
        """Sends a query to the device and returns the response."""
        if not self.instrument:
            logging.warning(f"Cannot query '{command}': Device {self.resource_name} not connected.")
            return None
        try:
            # logging.debug(f"QUERY to {self.resource_name}: {command}")
            response = self.instrument.query(command)
            # logging.debug(f"RESPONSE from {self.resource_name}: {response.strip()}")
            return response.strip()
        except visa.VisaIOError as e:
            logging.error(f"VISA Query Error to {self.resource_name} ('{command}'): {e}")
            # Consider attempting reconnect or raising exception
            raise
        except Exception as e:
             logging.error(f"Unexpected Query Error to {self.resource_name} ('{command}'): {e}")
             raise

    def clear(self):
        """Clears the device status."""
        if self.instrument:
             try:
                self.instrument.clear()
                time.sleep(0.1) # Short pause after clear
             except Exception as e:
                 logging.warning(f"Could not clear device {self.resource_name}: {e}")

    def wait_OPC(self):
        """Sends OPC? command."""
        # Avoid sending *WAI if not necessary or causing issues
        # Sometimes *OPC? is better for ensuring completion
        try:
            self.query("*OPC?")
        except Exception as e:
            logging.warning(f"Error during OPC query for {self.resource_name}: {e}")
            time.sleep(0.1) # Fallback delay

    def wait_WAI(self):
        """Sends *WAI command."""
        try:
            self.write("*WAI", wait_type = None)
        except Exception as e:
            logging.warning(f"Error during wait write for {self.resource_name}: {e}")
            time.sleep(0.1) # Fallback delay

    def set_output_state(self, output_num, state):
        """Sets the state (True/False) of a specific output."""
        state_str = 'ON' if state else 'OFF'
        self.write(f':OUTPut{output_num}:STATe {state_str}')
        logging.debug(f"Device {self.resource_name}: Output {output_num} set to {state_str}")

    def set_voltage(self, source_num, voltage):
        """Sets the voltage amplitude for a specific source."""
        # Add safety check if necessary, though main controller handles it
        # voltage = max(0, voltage) # Ensure non-negative voltage
        self.write(f':SOURce{source_num}:VOLTage {voltage:.4f}') # Use formatting for precision

    def get_voltage(self, source_num):
        """Queries the voltage amplitude for a specific source."""
        try:
            response = self.query(f':SOURce{source_num}:VOLTage?')
            return float(response)
        except (ValueError, TypeError, visa.VisaIOError) as e:
            logging.error(f"Error getting voltage for Source {source_num} on {self.resource_name}: {e}")
            return 0.0 # Return a default/safe value

    def apply_sinusoid(self, source_num, frequency, voltage):
        """Configures the source to output a sinusoid."""
        self.write(f':SOURce{source_num}:APPLy:SINusoid {frequency},{voltage:.4f}')

    def setup_defaults(self, defaults_config):
        """Applies default settings from the configuration."""
        logging.info(f"Setting up defaults for {self.resource_name}...")
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
            logging.debug(f"Device {self.resource_name}: Source {i} defaults applied.")
            # self.write(':SOURce%d:VOLTage:COUPle:STATe %d' % (i, 1)) # Is coupling needed? Check device manual

    def configure_trigger(self, source_num, trigger_source):
        """Configures the trigger source (e.g., 'BUS', 'EXTernal')."""
        self.write(f':TRIGger{source_num}:SOURce {trigger_source}')
        logging.debug(f"Device {self.resource_name}: Source {source_num} trigger set to {trigger_source}")


    def configure_output_trigger(self, output_num, state):
         """ Enables or disables the output trigger state (Master only typically)."""
         self.write(f':OUTPut{output_num}:TRIGger:STATe {1 if state else 0}')
         logging.debug(f"Device {self.resource_name}: Output {output_num} trigger state set to {state}")

    def trigger(self):
        """Sends a software trigger (*TRG)."""
        logging.info(f"Device {self.resource_name}: Software trigger sent.")
        self.write('*TRG')

    def abort(self):
        """Aborts operations."""
        self.write(':ABORt')
        logging.info(f"Device {self.resource_name}: Abort command sent.")

    def beep(self):
        """Triggers the system beeper."""
        try:
            self.write('SYSTem:BEEPer:IMMediate')
        except Exception as e:
            logging.warning(f"Could not trigger beep on {self.resource_name}: {e}")

    def __del__(self):
        # Ensure disconnection when the object is destroyed, although explicit disconnect is preferred
        # This might not run reliably in all Python exit scenarios.
        # self.disconnect()
        pass # Rely on explicit disconnect call