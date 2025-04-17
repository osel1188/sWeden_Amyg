# stim_controller.py
import json
import time
import threading
import keyboard
import numpy as np
import os
import sys
import logging
import pyvisa as visa # Import pyvisa here to close ResourceManager
from typing import Dict

from pathlib import Path

# homemade libraries
sys.path.append(str(Path(__file__).resolve().parent))
from keysight_edu import KeysightEDU
from keysight_edu_mockup import KeysightEDUMockup

# Configure logging (can be shared or configured per module)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class StimulationController:
    """
    Manages the stimulation experiment, controlling Keysight EDU devices.
    """
    # ANSI escape codes for colored output
    COLOR_RESET = "\033[0m"
    COLOR_YELLOW = "\033[33m"
    COLOR_RED_BOLD = "\033[1;31m"
    COLOR_MAGENTA = "\033[95m"
    COLOR_PROMPT_BG = "\033[38;5;220;48;5;18m"
    COLOR_INPUT = "\033[38;5;27m"

    def __init__(self, config_path='config.json', is_mock_up: bool = False):
        """
        Initializes the StimulationController.

        Args:
            config_path (str): Path to the JSON configuration file.
        """
        self.config = self._load_config(config_path)
        if not self.config:
             raise ValueError("Failed to load configuration.")

        self.rm = visa.ResourceManager() # Manage RM centrally
        self.devices: Dict[str, KeysightEDU] = self._initialize_devices(is_mock_up)
        self.target_voltages = np.zeros(self.config['channels']['total'])
        self.current_voltages = np.zeros(self.config['channels']['total'])
        self.stimulation_active = False
        self.emergency_stop_triggered = False
        self._keyboard_listener_thread = None
        self._stop_listener_flag = threading.Event()

    def _load_config(self, config_path):
        """Loads configuration from a JSON file."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            logging.info(f"Configuration loaded successfully from {config_path}")
            # Basic validation (add more as needed)
            if 'devices' not in config or 'master' not in config['devices'] or 'slave_1' not in config['devices']:
                 raise ValueError("Config missing required device definitions.")
            if 'ramp' not in config:
                 raise ValueError("Config missing ramp parameters.")
            if 'stimulation_params' not in config:
                 raise ValueError("Config missing stimulation parameters.")
            # make sure that the dictionary keys are upper case for future tests
            else:
                stimulation_params = config['stimulation_params']
                keys_to_uppercase = list(stimulation_params.keys())  # Important to get a static list
                for key in keys_to_uppercase:
                    stimulation_params[key.upper()] = stimulation_params.pop(key)
            return config
        except FileNotFoundError:
            logging.error(f"Configuration file not found: {config_path}")
            return None
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON configuration file {config_path}: {e}")
            return None
        except Exception as e:
            logging.error(f"An unexpected error occurred loading config {config_path}: {e}")
            return None


    def _initialize_devices(self, is_mock_up: bool = False):
        """Creates KeysightEDU instances based on the config."""
        devices = {}
        if not self.rm:
             logging.error("VISA Resource Manager not initialized.")
             return None

        dev_conf = self.config.get('devices', {})
        for name, conf in dev_conf.items():
             resource = conf.get('resource_name')
             if resource:
                 if is_mock_up:
                    devices[name] = KeysightEDUMockup(resource, conf) 
                 else:
                    devices[name] = KeysightEDU(resource, conf)
             else:
                 logging.warning(f"Resource name missing for device '{name}' in config.")
        return devices

    def _get_device_by_channel(self, channel_index):
        """ Gets the device object and its local source number for a global channel index """
        if not (0 <= channel_index < self.config['channels']['total']):
             raise IndexError(f"Channel index {channel_index} out of range.")
        mapping = self.config['channels']['mapping'][channel_index]
        device_name = mapping['device']
        source_num = mapping['source']
        device = self.devices.get(device_name)
        if not device:
            raise ValueError(f"Device '{device_name}' for channel {channel_index} not found.")
        return device, source_num

    def connect_devices(self):
        """Connects to all configured devices."""
        all_connected = True
        for name, device in self.devices.items():
            logging.info(f"Connecting to device: {name}")
            if not device.connect():
                logging.error(f"Failed to connect device: {name}")
                all_connected = False
                # Decide if partial connection is allowed or should abort
                # return False # Abort if any connection fails
        return all_connected

    def disconnect_devices(self):
        """Disconnects all devices."""
        logging.info("Disconnecting all devices...")
        for device in self.devices.values():
             if device:
                 device.disconnect()
        # Close the resource manager after all devices are done
        if self.rm:
             try:
                 self.rm.close()
                 logging.info("VISA Resource Manager closed.")
             except Exception as e:
                 logging.error(f"Error closing VISA Resource Manager: {e}")


    def setup_devices(self, condition):
        """Configures devices based on the stimulation condition (STIM/SHAM)."""
        condition = condition.upper()
        if condition not in self.config['stimulation_params']:
            logging.error(f"Invalid condition '{condition}'. Must be 'STIM' or 'SHAM'.")
            return False

        logging.info(f"Setting up devices for condition: {condition}")
        params = self.config['stimulation_params'][condition]
        defaults = self.config['device_defaults']
        master = self.devices.get('master')
        slave = self.devices.get('slave_1')

        if not master or not slave:
             logging.error("Master or Slave device not initialized.")
             return False

        try:
            # Apply specific frequencies for the condition (Voltage set to 0 initially)
            master.apply_sinusoid(1, params['master_freqs'][0], 0)
            master.apply_sinusoid(2, params['master_freqs'][1], 0)
            slave.apply_sinusoid(1, params['slave_freqs'][0], 0)
            slave.apply_sinusoid(2, params['slave_freqs'][1], 0)
            time.sleep(0.5)

            # Apply default settings (burst, load, etc.)
            master.setup_defaults(defaults)
            slave.setup_defaults(defaults)
            time.sleep(0.5)

            # Configure triggering (Master BUS triggers, Slave External)
            # Assuming source 1/2 trigger config applies to both sources on the device
            # Adjust if independent trigger config per source is needed
            master.configure_trigger(1, 'BUS')
            master.configure_trigger(2, 'BUS')
            # Enable master output trigger (linking master output 1 to slave trigger input)
            # Check Keysight docs for correct output trigger channel (often 1 or linked to CH1)
            master.configure_output_trigger(1, True) # Enable trigger out on master
            time.sleep(1) # Delay critical for trigger setup

            slave.configure_trigger(1, 'EXTernal')
            slave.configure_trigger(2, 'EXTernal')
            time.sleep(1) # Delay critical

            # Ensure outputs are initially OFF
            for dev in [master, slave]:
                for i in dev.config.get('output_channels', [1, 2]):
                    dev.set_output_state(i, False)

            logging.info("Device setup and trigger linking complete.")
            return True

        except Exception as e:
            logging.error(f"Error during device setup for {condition}: {e}")
            return False

    def get_target_voltages_from_user(self):
        """Prompts the user for target voltage amplitudes for each channel."""
        print(f"{self.COLOR_PROMPT_BG} Please insert measured reference voltage for each Channel for +/- 2mA {self.COLOR_RESET}")
        voltages = []
        max_v = self.config['safety']['max_voltage_amplitude']
        for i in range(self.config['channels']['total']):
             while True:
                 try:
                     prompt = f"{self.COLOR_INPUT}CHANNEL {i+1}: -> {self.COLOR_RESET}"
                     val_str = input(prompt).strip()
                     val = abs(float(val_str)) # Ensure positive
                     if val > max_v:
                          print(f"{self.COLOR_RED_BOLD}Amplitude {val}V exceeds safety limit of {max_v}V!{self.COLOR_RESET}")
                          # Optional: Ask again or abort
                          # return False # Abort if safety limit exceeded
                          continue # Ask again for this channel
                     voltages.append(val)
                     break # Valid input received
                 except ValueError:
                     print(f"{self.COLOR_RED_BOLD}Invalid input. Please enter a number.{self.COLOR_RESET}")
                 except EOFError:
                     print(f"\n{self.COLOR_RED_BOLD}Input interrupted. Exiting.{self.COLOR_RESET}")
                     return False

        self.target_voltages = np.array(voltages)
        print(f"{self.COLOR_YELLOW}Target voltages set: {self.target_voltages}{self.COLOR_RESET}")
        return True


    def ramp_voltage_1chan(self, chan, voltage, duration, rate, initialise=False, close_after=False):
        """ Ramps voltages smoothly across all channels. """
        if rate is not None and  rate <= 0:
            logging.warning("Ramp rate must be positive. No ramp up was made.")
            return
        elif duration is not None and  duration <= 0:
            logging.warning("Ramp duration must be positive. No ramp up was made.")
            return
        
        time_step_s = self.config['ramp']['time_step_ms'] / 1000.0
        self.config['channels']['mapping']
        self.channel_names = [channel_info['name'] for channel_info in self.config['channels']['mapping']]
        # Find the index using next() with a generator expression
        # It iterates through the list with indices (using enumerate)
        # and returns the index of the first item where channel_info['name'] matches
        # If no match is found, it returns the default value -1
        ch_idx, channel_info = next(
            ((index, channel_info) for index, channel_info in enumerate(self.config['channels']['mapping'])
            if channel_info['name'] == chan),
            -1  # Default value to return if the name is not found
        )
        if ch_idx == -1:
            logging.warning("Channel name couldn't be found within the configuration.")
            return

        start_voltage = float(np.copy(self.current_voltages[ch_idx]))
        voltage_gap = voltage - start_voltage

        if rate is not None:
            voltage_step = np.sign(voltage_gap) * rate * time_step_s
            num_steps = np.abs(int(voltage_gap / voltage_step))
            duration = num_steps * time_step_s
        elif duration is not None:
            num_steps = int(duration / time_step_s)
            if num_steps < 1: num_steps = 1 # Ensure at least one step
            voltage_step = voltage_gap / num_steps
        else:
            logging.warning("Ramp duration or rate must not be empty. No ramp up was made.")
            return
        num_steps = int(num_steps)
        if num_steps < 1: num_steps = 1 # Ensure at least one step

        dev = self.devices.get(channel_info['device'])
        if not dev:
            logging.error("Master or slave device not available.")
            return

        if initialise:
            dev.set_output_state(channel_info['source'], True)
            time.sleep(0.5) # Allow outputs to stabilize
            logging.info(f"Output {channel_info['device']}:{channel_info['source']} enabled.")
            self.devices.get('master').trigger()
            time.sleep(0.1) # Short delay after trigger before ramping

        spinner = ['◜', '◝', '◞', '◟']
        start_time = time.time()
        logging.info(f"Starting ramp to {voltage} over {duration}s...")
        try:
            for i in range(num_steps):
                if self.emergency_stop_triggered:
                    logging.warning("Ramp interrupted by emergency stop.")
                    break

                step_start_time = time.perf_counter() # More precise timer for sleep calculation

                sys.stdout.flush()
                progress = (i + 1) / num_steps * 100
                next_voltage = start_voltage + (voltage_step * (i + 1))
                # Clamp voltages to be non-negative and apply
                v = max(0, next_voltage) # Ensure non-negative
                self.current_voltages[ch_idx] = v # Update internal state *before* sending
                sys.stdout.write(f'\r Ramping ..... {spinner[i%4]} {progress:.1f}%: voltage = {v} V')

                try:
                    dev.set_voltage(channel_info['source'], v)
                except Exception as e:
                    logging.error(f"Error setting voltage on channel {channel_info['device']}-{channel_info['source']}: {e}")
                    # Decide how to handle: stop ramp, skip channel, etc.
                    self.emergency_stop() # Safest option
                    return # Exit ramp function

                # Calculate sleep time to maintain overall duration
                elapsed_step = time.perf_counter() - step_start_time
                sleep_time = max(0, time_step_s - elapsed_step)
                time.sleep(sleep_time)

            # Final step: Ensure exact target voltage is set
            if not self.emergency_stop_triggered:
                sys.stdout.write(f'\r Ramping ..... Done. 100.0%                                       \n')
                v = max(0, voltage)
                self.current_voltages[ch_idx] = v
                try:
                    device, source_num = self._get_device_by_channel(ch_idx)
                    device.set_voltage(source_num, v)
                except Exception as e:
                    logging.error(f"Error setting final voltage on channel {ch_idx+1}: {e}")
                    self.emergency_stop()
                logging.info(f"Ramp finished in {time.time() - start_time:.2f}s. Final Voltages: {voltage}")
            else:
                 print("\n Ramp stopped prematurely.")

            if close_after:
                dev.set_output_state(channel_info['source'], False)
                time.sleep(.5)
                logging.info(f"Output {channel_info['device']}:{channel_info['source']} disabled.")
                dev.write('*WAI')
                time.sleep(.5)
                self.devices.get('master').write(f':ABORt')
                logging.info(f"Master trigger disabled.")
                time.sleep(0.1) # Short delay 


        except KeyboardInterrupt:
             print("\n Ramp interrupted by user (Ctrl+C).")
             self.emergency_stop() # Treat Ctrl+C during ramp as emergency
        except Exception as e:
             logging.error(f"Unexpected error during ramp: {e}")
             self.emergency_stop()
        finally:
            sys.stdout.flush() # Ensure prompt is clean


    def _ramp_voltage(self, target_voltages, duration):
        """ Ramps voltages smoothly across all channels. """
        if duration <= 0:
             logging.warning("Ramp duration must be positive. No ramp up was made.")
             return

        time_step_s = self.config['ramp']['time_step_ms'] / 1000.0
        num_steps = int(duration / time_step_s)
        if num_steps < 1: num_steps = 1 # Ensure at least one step

        start_voltages = np.copy(self.current_voltages)
        voltage_steps = (np.array(target_voltages) - start_voltages) / num_steps

        spinner = ['◜', '◝', '◞', '◟']
        start_time = time.time()

        logging.info(f"Starting ramp to {target_voltages} over {duration}s...")
        try:
            for i in range(num_steps):
                if self.emergency_stop_triggered:
                    logging.warning("Ramp interrupted by emergency stop.")
                    break

                step_start_time = time.perf_counter() # More precise timer for sleep calculation

                sys.stdout.flush()
                progress = (i + 1) / num_steps * 100
                sys.stdout.write(f'\r Ramping ..... {spinner[i%4]} {progress:.1f}% ')

                next_voltages = start_voltages + (voltage_steps * (i + 1))
                # Clamp voltages to be non-negative and apply
                for ch_idx in range(len(next_voltages)):
                    v = max(0, next_voltages[ch_idx]) # Ensure non-negative
                    self.current_voltages[ch_idx] = v # Update internal state *before* sending
                    try:
                        device, source_num = self._get_device_by_channel(ch_idx)
                        device.set_voltage(source_num, v)
                    except Exception as e:
                        logging.error(f"Error setting voltage on channel {ch_idx+1}: {e}")
                        # Decide how to handle: stop ramp, skip channel, etc.
                        self.emergency_stop() # Safest option
                        return # Exit ramp function


                # Calculate sleep time to maintain overall duration
                elapsed_step = time.perf_counter() - step_start_time
                sleep_time = max(0, time_step_s - elapsed_step)
                time.sleep(sleep_time)

            # Final step: Ensure exact target voltage is set
            if not self.emergency_stop_triggered:
                 sys.stdout.write(f'\r Ramping ..... Done. 100.0% \n')
                 for ch_idx, target_v in enumerate(target_voltages):
                     v = max(0, target_v)
                     self.current_voltages[ch_idx] = v
                     try:
                          device, source_num = self._get_device_by_channel(ch_idx)
                          device.set_voltage(source_num, v)
                     except Exception as e:
                          logging.error(f"Error setting final voltage on channel {ch_idx+1}: {e}")
                          self.emergency_stop()
                 logging.info(f"Ramp finished in {time.time() - start_time:.2f}s. Final Voltages: {self.current_voltages}")

            else:
                 print("\n Ramp stopped prematurely.")


        except KeyboardInterrupt:
             print("\n Ramp interrupted by user (Ctrl+C).")
             self.emergency_stop() # Treat Ctrl+C during ramp as emergency
        except Exception as e:
             logging.error(f"Unexpected error during ramp: {e}")
             self.emergency_stop()
        finally:
            sys.stdout.flush() # Ensure prompt is clean


    def start_stimulation(self):
        """Turns on outputs, triggers devices, and ramps up voltage."""
        if self.stimulation_active:
            print(f"{self.COLOR_YELLOW}Stimulation is already active.{self.COLOR_RESET}")
            return
        if self.emergency_stop_triggered:
             print(f"{self.COLOR_RED_BOLD}Cannot start stimulation, emergency stop was triggered.{self.COLOR_RESET}")
             return

        # Check if starting from non-zero (optional, based on original script logic)
        if np.any(self.current_voltages > 0.01): # Use a small tolerance
            print(f"{self.COLOR_RED_BOLD}Cannot ramp up from non-zero voltage as starting point! Current voltages: {self.current_voltages}{self.COLOR_RESET}")
            print(f"{self.COLOR_YELLOW}Please end ('e') the stimulation first to ramp down.{self.COLOR_RESET}")
            return

        logging.info("Starting stimulation sequence...")
        master = self.devices.get('master')
        slave = self.devices.get('slave_1')
        if not master or not slave:
            logging.error("Master or slave device not available.")
            return

        try:
            master.set_output_state(1, True)
            master.set_output_state(2, True)
            slave.set_output_state(1, True)
            slave.set_output_state(2, True)
            logging.info("Outputs enabled.")
            time.sleep(0.5) # Allow outputs to stabilize
            master.wait_WAI()
            slave.wait_WAI()
            time.sleep(0.5) # Allow outputs to stabilize
            
            # Send software trigger to Master
            master.trigger()
            time.sleep(0.1) # Short delay after trigger before ramping

            # Ramp up
            ramp_duration = self.config['ramp']['duration_seconds']
            self._ramp_voltage(self.target_voltages, ramp_duration)

            if not self.emergency_stop_triggered:
                 self.stimulation_active = True
                 logging.info(f"{self.COLOR_YELLOW}Ramping up finished. Stimulation active.{self.COLOR_RESET}")


        except Exception as e:
            logging.error(f"Error during stimulation start: {e}")
            self.emergency_stop() # Trigger emergency stop on error during start

    def end_stimulation(self):
        """Ramps down voltage, aborts triggers, and turns off outputs."""
        if not self.stimulation_active and np.all(self.current_voltages < 0.01):
            print(f"{self.COLOR_YELLOW}Stimulation is not active or already at zero.{self.COLOR_RESET}")
            return

        logging.info("Ending stimulation sequence...")
        master = self.devices.get('master')
        slave = self.devices.get('slave_1')
        if not master or not slave:
            logging.error("Master or slave device not available.")
            return

        try:
            # Ramp down to zero
            ramp_duration = self.config['ramp']['duration_seconds']
            zero_voltages = np.zeros(self.config['channels']['total'])
            self._ramp_voltage(zero_voltages, ramp_duration)

            # Wait for ramp down to complete visually/audibly if needed
            time.sleep(1.0)

            # Abort triggers on both devices
            master.abort()
            slave.abort()
            time.sleep(0.2)

            # Turn off outputs
            for dev in [master, slave]:
                for i in dev.config.get('output_channels', [1, 2]):
                    dev.set_output_state(i, False)
            logging.info("Outputs disabled.")

            # Clear device status
            master.clear()
            slave.clear()

            self.stimulation_active = False
            logging.info(f"{self.COLOR_YELLOW}Ramping down finished. Stimulation ended.{self.COLOR_RESET}")

        except Exception as e:
            logging.error(f"Error during stimulation end: {e}")
            # Attempt to turn off outputs even if other steps fail
            self.emergency_stop(is_error=True)


    def beep_devices(self):
        """Makes both devices beep twice."""
        master = self.devices.get('master')
        slave = self.devices.get('slave_1')
        if not master or not slave:
            logging.warning("Cannot beep, devices not available.")
            return
        try:
            master.beep()
            slave.beep()
            master.wait_OPC() # Ensure beep command sent before next
            slave.wait_OPC()
            time.sleep(0.15)
            master.beep()
            slave.beep()
        except Exception as e:
            logging.error(f"Error during beeping sequence: {e}")


    def _listen_for_emergency_stop(self):
        """Worker function for the keyboard listener thread."""
        logging.info("Keyboard listener started for emergency stop ('u').")
        while not self._stop_listener_flag.is_set():
            try:
                # Use keyboard.read_key() for blocking read or check is_pressed in loop
                if keyboard.is_pressed('u'):
                    if not self.emergency_stop_triggered: # Prevent multiple triggers
                         print(f"\n{self.COLOR_RED_BOLD}[U] Emergency stop key pressed!{self.COLOR_RESET}")
                         self.emergency_stop()
                         # Signal the main loop to potentially exit or handle
                         break # Exit listener loop once triggered
                time.sleep(0.05) # Small delay to prevent high CPU usage
            except ImportError:
                 logging.warning("Keyboard library not available. Emergency stop key 'u' disabled.")
                 break # Stop listening if library fails
            except Exception as e:
                 # Catch potential errors within the thread
                 logging.error(f"Error in keyboard listener thread: {e}")
                 time.sleep(1) # Avoid busy-looping on error


    def start_keyboard_listener(self):
        """Starts the keyboard listener in a separate thread."""
        if self._keyboard_listener_thread is not None and self._keyboard_listener_thread.is_alive():
             logging.warning("Keyboard listener already running.")
             return

        # Reset flags before starting
        self.emergency_stop_triggered = False
        self._stop_listener_flag.clear()

        self._keyboard_listener_thread = threading.Thread(target=self._listen_for_emergency_stop, daemon=True)
        self._keyboard_listener_thread.start()

    def stop_keyboard_listener(self):
        """Signals the keyboard listener thread to stop."""
        logging.info("Stopping keyboard listener...")
        self._stop_listener_flag.set()
        if self._keyboard_listener_thread is not None:
             # Wait briefly for the thread to notice the flag
             self._keyboard_listener_thread.join(timeout=0.5)
             if self._keyboard_listener_thread.is_alive():
                  logging.warning("Keyboard listener thread did not stop gracefully.")
        self._keyboard_listener_thread = None


    def emergency_stop(self, is_error=False):
        """Immediately stops all outputs and disconnects (called by listener or error)."""
        if self.emergency_stop_triggered and not is_error: # Allow re-trigger on new error
             return # Already handled

        self.emergency_stop_triggered = True
        self.stimulation_active = False # Ensure state reflects stop

        print(f"\n{self.COLOR_RED_BOLD}!!! EMERGENCY STOP TRIGGERED !!!{self.COLOR_RESET}")
        print(f"{self.COLOR_RED_BOLD}Attempting to stop all outputs immediately...{self.COLOR_RESET}")

        # Directly try to turn off outputs, ignoring potential errors during stop
        for name, device in self.devices.items():
            if device and device.instrument: # Check if device and instrument exist
                print(f"Stopping outputs on {name}...")
                try:
                    # Abort ongoing operations first might be safer
                    device.abort()
                    time.sleep(0.1)
                except Exception as e:
                     print(f"{self.COLOR_YELLOW}Warning: Could not abort {name}: {e}{self.COLOR_RESET}")

                for i in device.config.get('output_channels', [1, 2]):
                    try:
                        # Send OFF command directly
                        device.instrument.write(f':OUTPut{i}:STATe OFF')
                        time.sleep(0.05) # Small delay between commands
                    except Exception as e:
                        print(f"{self.COLOR_YELLOW}Warning: Could not turn off output {i} on {name}: {e}{self.COLOR_RESET}")

        print(f"{self.COLOR_RED_BOLD}Outputs commanded OFF.{self.COLOR_RESET}")
        print(f"{self.COLOR_RED_BOLD}Exiting application due to emergency stop.{self.COLOR_RESET}")

        # Stop the listener thread if it's running and didn't trigger this
        self.stop_keyboard_listener()

        # Disconnect devices (best effort)
        self.disconnect_devices()

        # Force exit the application
        os._exit(1) # Use os._exit for immediate termination from thread/emergency


    def run(self):
        """Main application loop."""
        print(f"{self.COLOR_MAGENTA}=== Stimulation Control System ===")
        if not self.devices:
             print(f"{self.COLOR_RED_BOLD}Initialization failed. Check config and connections.{self.COLOR_RESET}")
             return

        if not self.connect_devices():
             print(f"{self.COLOR_RED_BOLD}Failed to connect to all devices. Exiting.{self.COLOR_RESET}")
             self.disconnect_devices() # Attempt cleanup
             return

        # Get Condition (STIM/SHAM)
        while True:
            try:
                 cond = input("Select condition [STIM / SHAM]: ").upper().strip()
                 if cond in self.config['stimulation_params']:
                     break
                 else:
                     print(f"{self.COLOR_RED_BOLD}Invalid condition. Please enter STIM or SHAM.{self.COLOR_RESET}")
            except EOFError:
                 print(f"\n{self.COLOR_RED_BOLD}Input interrupted. Exiting.{self.COLOR_RESET}")
                 self.cleanup()
                 return
            except KeyboardInterrupt:
                print(f"\n{self.COLOR_YELLOW}Operation cancelled by user.{self.COLOR_RESET}")
                self.cleanup()
                return


        if not self.setup_devices(cond):
            print(f"{self.COLOR_RED_BOLD}Failed to set up devices for {cond}. Exiting.{self.COLOR_RESET}")
            self.cleanup()
            return

        if not self.get_target_voltages_from_user():
             print(f"{self.COLOR_RED_BOLD}Failed to get valid target voltages. Exiting.{self.COLOR_RESET}")
             self.cleanup()
             return

        # Start background listener AFTER essential setup
        self.start_keyboard_listener()

        print(f"{self.COLOR_MAGENTA}🔬 System ready. Amplitude vectors aligned.{self.COLOR_RESET}")

        try:
            while not self.emergency_stop_triggered:
                try:
                    action = input(f"[{self.COLOR_YELLOW}s{self.COLOR_RESET}]tart, "
                                   f"[{self.COLOR_YELLOW}e{self.COLOR_RESET}]nd, "
                                   f"[{self.COLOR_YELLOW}b{self.COLOR_RESET}]eep, "
                                   f"[{self.COLOR_YELLOW}q{self.COLOR_RESET}]uit "
                                   f"(Emergency Stop: press '{self.COLOR_RED_BOLD}u{self.COLOR_RESET}') :: ").lower().strip()

                    if action == 's':
                         self.start_stimulation()
                    elif action == 'e':
                         self.end_stimulation()
                    elif action == 'b':
                         self.beep_devices()
                    elif action == 'q':
                         print("Quit command received.")
                         break # Exit main loop gracefully
                    else:
                         print(f"{self.COLOR_RED_BOLD}Invalid command.{self.COLOR_RESET}")

                except EOFError: # Handle Ctrl+D
                     print(f"\n{self.COLOR_YELLOW}Input stream closed. Exiting gracefully...{self.COLOR_RESET}")
                     break
                except KeyboardInterrupt: # Handle Ctrl+C in main loop
                     print(f"\n{self.COLOR_YELLOW}Operation interrupted by user (Ctrl+C). Exiting gracefully...{self.COLOR_RESET}")
                     break

        finally:
             self.cleanup()


    def cleanup(self):
         """Gracefully shuts down the system."""
         print("Initiating shutdown sequence...")
         self.stop_keyboard_listener()

         # Ensure stimulation is ended (ramped down) if active
         if self.stimulation_active:
             print("Stimulation was active, attempting graceful ramp down...")
             try:
                 self.end_stimulation()
             except Exception as e:
                 print(f"{self.COLOR_RED_BOLD}Error during final ramp down: {e}. Proceeding with disconnect.{self.COLOR_RESET}")
                 # Attempt emergency off just in case ramp down failed badly
                 for name, device in self.devices.items():
                     if device and device.instrument:
                         for i in device.config.get('output_channels', [1, 2]):
                              try: device.instrument.write(f':OUTPut{i}:STATe OFF')
                              except: pass # Ignore errors here, best effort

         # Final beep sequence
         print("Final beep.")
         try:
             self.beep_devices()
             time.sleep(0.5) # Allow time for final beep
         except Exception:
             pass # Ignore errors during final beep

         self.disconnect_devices()
         print("System shutdown complete.")