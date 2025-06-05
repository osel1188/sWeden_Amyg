# stim_controller_gui.py
import tkinter as tk
import logging
import numpy as np
import time
import threading # Import threading if needed for ramp
import os
import sys
from pathlib import Path

from tkinter import ttk

# homemade libraries
sys.path.append(str(Path(__file__).resolve().parent))
from lib.UI_device_control.stim_controller import StimulationController
from lib.UI_device_control.GUI.stim_controller_gui import ControllerGUI

# Configure logging (optional, GUI provides feedback)
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class StimulationController_withGUI(StimulationController):
    """
    StimulationController adapted for a Tkinter GUI.
    Inherits core logic from StimulationController.
    """
    def __init__(self, config_path='config.json', 
                 condition: str = None, 
                 participant_folder: str = None,
                 enable_keyboard_shortcut: bool = False, is_mock_up: bool = False):
        super().__init__(config_path=config_path, 
                         participant_folder=participant_folder,
                         is_mock_up=is_mock_up)
        self.root = None
        self.gui = None
        # Override the status update mechanism to use the GUI
        self._status_update_func = self._print_status_fallback # Default if GUI not ready
        self._enable_keyboard_shortcut = enable_keyboard_shortcut        
        # a condition was initially given, adjust to the GUI expected values
        if condition:
            if condition == "sham":
                self._condition = "SHAM"
            elif condition == "active":
                self._condition = "STIM"
        else:
            self._condition = None

    def run(self):
        """Starts the GUI application."""
        self.root = tk.Tk()
        # Set up GUI styling theme (optional, place before creating GUI instance)
        style = ttk.Style(self.root)
        try:
            # Choose a theme ('clam', 'alt', 'default', 'vista', etc.)
            # Available themes depend on your OS and Tk installation
            available_themes = style.theme_names()
            # print("Available themes:", available_themes) # Uncomment to see themes
            if 'clam' in available_themes:
                 style.theme_use('clam')
            elif 'vista' in available_themes: # Good fallback on Windows
                 style.theme_use('vista')
        except tk.TclError:
             print("Warning: Could not set preferred ttk theme.")

        self.gui = ControllerGUI(self.root, self, 
                                 log_folder_path=self._participant_folder)
        self._status_update_func = self.gui.update_status # Link to GUI's update method

        # Start keyboard listener AFTER GUI is created
        if self._enable_keyboard_shortcut:
            super().start_keyboard_listener() # Call parent's method

        # a condition was initially given, proceed connection and condition setup
        if self._condition:
            self.gui.condition_var.set(self._condition)
            self.gui.set_hide_mode(True)
            self.gui_confirm_condition()

        self.root.mainloop() # Start the Tkinter event loop

        # Code here runs after the mainloop exits (window closed)
        logging.info("GUI main loop exited.")
        # Cleanup should have been called by on_closing/quit handler


    # --- GUI Action Handlers ---
    # These methods are called by buttons in the GUI
    def gui_confirm_condition(self):
        """Handles the 'Confirm Condition' button click."""
        self.gui.disable_all_controls() # Disable during connection/setup
        self._condition = self.gui.condition_var.get()
        if self.gui.hide_mode_var.get() == True:
            self._status_update_func(f"Condition X selected. Connecting devices...", "info")
        else:
            self._status_update_func(f"Condition '{self._condition}' selected. Connecting devices...", "info")

        # Run connection and setup in a separate thread to avoid blocking GUI?
        # For simplicity now, we do it directly but update status
        if not self.connect_devices():
            self._status_update_func("Failed to connect to devices. Check connections and config.", "error")
            self.gui.enable_condition_selection() # Allow trying again
            return

        self._status_update_func("Devices connected. Setting up for condition...", "info")
        if not self.setup_devices(self._condition):
             self._status_update_func(f"Failed to set up devices for {self._condition}.", "error")
             # Consider disconnect or just allow re-confirm?
             self.gui.enable_condition_selection()
             return

        self._status_update_func("Device setup complete. Please enter target voltages.", "success")
        self.gui.disable_condition_selection() # Condition confirmed
        self.gui.enable_voltage_input()
        # Enable beep now that devices are connected
        self.gui.set_widget_state("beep_button", tk.NORMAL)


    def set_voltages(self, voltages):
        if voltages is not None:
             self.target_voltages = np.array(voltages)
             self._status_update_func(f"Target voltages set: {self.target_voltages}", "success")
             self.gui.disable_voltage_input()
             # Enable main controls now that voltages are set
             self.gui.enable_stimulation_controls(is_active=self.stimulation_active)
        else:
             # Error message shown by get_voltages
             self._status_update_func("Invalid voltages entered.", "warning")

    def gui_start_stimulation(self):
        """Handles the 'Start Stimulation' button click."""
        if self.stimulation_active:
            self._status_update_func("Stimulation is already active.", "warning")
            return
        if self.emergency_stop_triggered:
             self._status_update_func("Cannot start: Emergency stop was triggered.", "error")
             return
        if np.any(self.current_voltages > 0.01):
            self._status_update_func("Cannot ramp up from non-zero voltage. Please 'End Stimulation' first.", "warning")
            return

        self._status_update_func("Starting stimulation sequence...", "info")
        self.gui.disable_all_controls() # Disable controls during start/ramp

        # --- Option 1: Run in main thread (simpler, GUI might freeze during ramp) ---
        # self.start_stimulation() # Call the original method
        # if self.stimulation_active: # Check if successful (not stopped by error)
        #     self.gui.enable_stimulation_controls(is_active=True)
        # else: # Failed or emergency stopped during ramp
        #     self.gui.disable_all_controls() # Keep disabled if error
        #     if not self.emergency_stop_triggered: # Enable condition if not emergency
        #          self.gui.enable_condition_selection()


        # --- Option 2: Run start/ramp in a separate thread (better for GUI responsiveness) ---
        thread = threading.Thread(target=self._start_stimulation_thread, daemon=True)
        thread.start()


    def _start_stimulation_thread(self):
        """Helper method to run start_stimulation logic in a thread."""
        try:
            # Call the core logic from the parent class directly
            # This avoids recursively calling the overridden method
            super().start_stimulation() # This contains the checks, output on, trigger, ramp
        except Exception as e:
            self._status_update_func(f"Error during stimulation start thread: {e}", "error")
            # Ensure GUI state reflects error - potentially call emergency stop logic
            self.emergency_stop(is_error=True) # Trigger stop on error
        finally:
            # Update GUI state based on outcome (needs to be scheduled in main thread)
            if self.root and self.root.winfo_exists():
                self.root.after(0, self._update_gui_after_start)


    def _update_gui_after_start(self):
        """Updates GUI state after start_stimulation thread finishes."""
        if self.stimulation_active: # Check if successful (not stopped by error)
            self.gui.enable_stimulation_controls(is_active=True)
        else: # Failed or emergency stopped during ramp
            self.gui.disable_all_controls() # Keep disabled if error
            if not self.emergency_stop_triggered: # Enable condition if not emergency
                 # What state should we return to? Allow re-confirm?
                 self.gui.enable_condition_selection()
                 self.gui.set_widget_state("beep_button", tk.NORMAL)



    def gui_end_stimulation(self):
        """Handles the 'End Stimulation' button click."""
        if not self.stimulation_active and np.all(self.current_voltages < 0.01):
            self._status_update_func("Stimulation is not active or already at zero.", "warning")
            return

        self._status_update_func("Ending stimulation sequence...", "info")
        self.gui.disable_all_controls() # Disable controls during end/ramp

        # --- Option 1: Run in main thread ---
        # self.end_stimulation() # Call the original method
        # self.gui.enable_stimulation_controls(is_active=False)

        # --- Option 2: Run in a separate thread ---
        thread = threading.Thread(target=self._end_stimulation_thread, daemon=True)
        thread.start()


    def _end_stimulation_thread(self):
        """Helper method to run end_stimulation logic in a thread."""
        try:
            # Call the core logic from the parent class
            super().end_stimulation()
        except Exception as e:
            self._status_update_func(f"Error during stimulation end thread: {e}", "error")
            self.emergency_stop(is_error=True)
        finally:
            if self.root and self.root.winfo_exists():
                self.root.after(0, self._update_gui_after_end)

    def _update_gui_after_end(self):
        """Updates GUI state after end_stimulation thread finishes."""
        # Re-enable controls for potentially starting again
        self.gui.enable_stimulation_controls(is_active=False)


    def gui_beep_devices(self):
        """Handles the 'Beep Devices' button click."""
        self._status_update_func("Beeping devices...", "info")
        # Beeping is fast, can run directly
        super().beep_devices() # Call parent method

    def gui_quit(self):
        """Handles the 'Quit' button click or window close."""
        self._status_update_func("Quit requested. Cleaning up...", "info")
        self.gui.disable_all_controls()
        # Run cleanup in thread? It involves ramp down, so maybe.
        # For now, direct call, but acknowledge potential GUI freeze
        try:
             self.cleanup() # Call parent's cleanup
        except Exception as e:
             self._status_update_func(f"Error during cleanup: {e}", "error")
        finally:
            # Ensure listener stops even if cleanup fails
            self.stop_keyboard_listener()
            if self.root:
                self.root.destroy() # Close the GUI window


    # --- Overridden Methods from StimulationController ---
    def _ramp_voltage(self, target_voltages, duration, preview=True, disable_keyboard_interrupt=True):
        """ Override cleanup to potentially update GUI before parent logic """
        self._status_update_func("Initiating shutdown sequence...", "info")
        # Parent cleanup handles ramp down, disconnect etc. It will call end_stimulation
        # which calls _ramp_voltage, which updates the GUI.
        super()._ramp_voltage(target_voltages, duration, preview=preview, disable_keyboard_interrupt=disable_keyboard_interrupt)

    def emergency_stop(self, is_error=False):
        """ Override to update GUI state and handle exit """
        if self.emergency_stop_triggered and not is_error:
             return

        # Update GUI immediately if possible
        if self.gui:
            self.root.after(0, self.gui.show_emergency_stop_state)
        else:
             print("!!! EMERGENCY STOP (GUI NOT READY) !!!")

        # Call original logic (stops outputs, etc.) but prevent it from os._exit
        # Temporarily modify the parent's method or handle exit here
        print("!!! EMERGENCY STOP TRIGGERED !!!")
        print("Attempting to stop all outputs immediately...")
        self.emergency_stop_triggered = True # Set flag early
        self.stimulation_active = False

        # Simplified stop logic here - parent class might be complex
        for name, device in self.devices.items():
            if device and device.instrument:
                print(f"Stopping outputs on {name}...")
                try: device.abort()
                except: pass
                for i in device.config.get('output_channels', [1, 2]):
                    try: device.instrument.write(f':OUTPut{i}:STATe OFF')
                    except: pass

        print("Outputs commanded OFF.")
        print("Application will close.")

        # Stop listener
        self.stop_keyboard_listener()

        # Close GUI window after a short delay to show the red screen
        if self.root:
            self.root.after(2000, self.root.destroy) # Close after 2s

        # Don't call os._exit here; let the GUI close normally if possible.
        # If called from background thread, os._exit might still be necessary.

    def cleanup(self):
        """ Override cleanup to potentially update GUI before parent logic """
        self._status_update_func("Initiating shutdown sequence...", "info")
        # Parent cleanup handles ramp down, disconnect etc. It will call end_stimulation
        # which calls _ramp_voltage, which updates the GUI.
        super().cleanup()
        self._status_update_func("System shutdown complete.", "info")