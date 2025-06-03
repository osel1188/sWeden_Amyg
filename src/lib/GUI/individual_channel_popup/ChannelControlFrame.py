from __future__ import annotations # MUST be the first non-comment line

import tkinter as tk
from tkinter import ttk, messagebox

import os
import sys
from pathlib import Path
import typing
import random # Added for default values
import math # Added for checking voltage close to zero

if typing.TYPE_CHECKING:
    # To avoid circular imports during type checking or for IDEs
    # Assume these paths are correctly set up in your project structure
    # sys.path.append(str(Path(__file__).resolve().parent))
    # sys.path.append(str(Path(__file__).resolve().parent.parent))
    try:
        sys.path.append(str(Path(__file__).resolve().parent))
        sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
        from TargetVoltageSettings_Popup import TargetVoltageSettings_Popup
        from lib.GUI.controller_gui import ControllerGUI
        from lib.stim_controller_with_gui import StimulationController_withGUI
    except ImportError:
        # Define dummy types if imports fail during static analysis
        TargetVoltageSettings_Popup = typing.TypeVar('TargetVoltageSettings_Popup')
        ControllerGUI = typing.TypeVar('ControllerGUI')
        StimulationController_withGUI = typing.TypeVar('StimulationController_withGUI')


# --- Constants ---
LED_SIZE = 15 # Size for the LED squares
COLOR_LED_RED = "red"
COLOR_LED_GREEN = "lime green" # Brighter green
COLOR_LED_OFF = "gray" # Or default background color
UPDATE_INTERVAL = 500 # Milliseconds for updating current voltage display
VOLTAGE_ZERO_THRESHOLD = 0.01 # Threshold below which voltage is considered "zero" for LED


class ChannelControlFrame(ttk.Frame):
    """
    Frame containing controls (voltage, ramp, buttons, LEDs) for a single channel.
    Includes display of current voltage and status LEDs for saved state and current voltage.
    """
    def __init__(self, master: TargetVoltageSettings_Popup, controller: StimulationController_withGUI,
                 channel_index: int, channel_name: str, max_voltage: float, initial_data: dict | None = None):
        """
        Initializes the frame for a single channel.

        Args:
            master: The parent window (TargetVoltageSettings_Popup instance).
            controller: The StimulationController_withGUI instance.
            channel_index: The numerical index of this channel.
            channel_name: The name of this channel (e.g., "C1").
            max_voltage: The maximum allowed voltage from config.
            initial_data: Optional dictionary with pre-saved data for this channel.
        """
        super().__init__(master, borderwidth=2, relief=tk.GROOVE, padding="10")
        self.master_popup = master # Reference to the main popup
        self.controller = controller
        self.channel_index = channel_index
        self.channel_name = channel_name
        self.max_voltage = max_voltage

        # --- Widget Variables for this channel ---
        self.target_voltage_var = tk.StringVar()
        self.ramp_parameter_choice = tk.StringVar(value="rate") # 'duration' or 'rate'
        self.duration_var = tk.StringVar()
        self.rate_var = tk.StringVar()
        self.current_voltage_var = tk.StringVar(value="?.?? V") # Variable for current voltage display

        # --- State Tracking for this channel ---
        self._save_state_led_state = 'red' # 'red' or 'green' for saved settings validity
        self.saved_data: dict | None = None # Holds the last successfully validated & saved data

        self._create_widgets()
        self.load_data(initial_data) # Load initial data or set defaults

        self._update_entry_states() # Set initial state of duration/rate entries
        self._update_save_state_led_display() # Set initial save state LED color


    def _create_widgets(self):
        """Creates and arranges widgets within this channel's frame."""

        # --- Header: Channel Name, Current Voltage Display, and Voltage LED ---
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, pady=(0, 10), anchor=tk.W)

        ttk.Label(header_frame, text=f"Channel: {self.channel_name}", font="-weight bold").pack(side=tk.LEFT, padx=(0, 5))

        # Current Voltage Display Label (Requirements 1)
        self.current_voltage_label = ttk.Label(header_frame, textvariable=self.current_voltage_var, width=8, anchor=tk.W, relief=tk.SUNKEN, borderwidth=1)
        self.current_voltage_label.pack(side=tk.LEFT, padx=(0, 5))

        # New LED for Current Voltage Status (Requirement 3)
        self.voltage_led_canvas = tk.Canvas(header_frame, width=LED_SIZE, height=LED_SIZE,
                                            borderwidth=1, relief=tk.RAISED)
        self.voltage_led_canvas.pack(side=tk.LEFT, padx=(0, 10))
        # Initial drawing (will be updated by _update_current_voltage_display)
        self._update_voltage_led_display(COLOR_LED_OFF) # Start as off/gray


        # --- Target Voltage Input ---
        voltage_frame = ttk.Frame(self)
        voltage_frame.pack(fill=tk.X, pady=5)
        ttk.Label(voltage_frame, text="Target Voltage (V):").grid(row=0, column=0, sticky=tk.W, padx=(0, 5))
        self.voltage_entry = ttk.Entry(voltage_frame, textvariable=self.target_voltage_var, width=8)
        self.voltage_entry.grid(row=0, column=1, sticky=tk.W)
        # Add trace to turn save state LED red when target voltage is modified
        self.target_voltage_var.trace_add("write", self._mark_unsaved)
        ttk.Label(voltage_frame, text=f"(Max: {self.max_voltage})").grid(row=0, column=2, sticky=tk.W, padx=(5, 0))


        # --- Ramping Parameters Input ---
        ramp_frame = ttk.LabelFrame(self, text="Ramp Parameter", padding=(10, 5))
        ramp_frame.pack(fill=tk.X, pady=5)

        duration_radio = ttk.Radiobutton(ramp_frame, text="Duration (s):", variable=self.ramp_parameter_choice,
                                         value="duration", command=self._update_entry_states)
        rate_radio = ttk.Radiobutton(ramp_frame, text="Rate (V/s):", variable=self.ramp_parameter_choice,
                                     value="rate", command=self._update_entry_states)
        self.duration_entry = ttk.Entry(ramp_frame, textvariable=self.duration_var, width=8)
        self.rate_entry = ttk.Entry(ramp_frame, textvariable=self.rate_var, width=8)

        # Add traces to turn save state LED red when ramp parameters are modified
        self.duration_var.trace_add("write", self._mark_unsaved)
        self.rate_var.trace_add("write", self._mark_unsaved)
        self.ramp_parameter_choice.trace_add("write", self._mark_unsaved)

        duration_radio.grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.duration_entry.grid(row=0, column=1, padx=5, pady=2)
        rate_radio.grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.rate_entry.grid(row=1, column=1, padx=5, pady=2)

        # --- Buttons and Save State LED ---
        button_frame = ttk.Frame(self, padding=(0, 10, 0, 0))
        button_frame.pack(fill=tk.X)

        self.apply_button = ttk.Button(button_frame, text="Apply", command=self._on_apply)
        self.save_button = ttk.Button(button_frame, text="Save", command=self._on_save)
        self.stop_button = ttk.Button(button_frame, text="Stop (0V)", command=self._on_stop)

        # Save State LED Canvas (Moved here - Requirement 2)
        self.save_state_led_canvas = tk.Canvas(button_frame, width=LED_SIZE, height=LED_SIZE,
                                               borderwidth=1, relief=tk.RAISED) # Match background

        # Layout buttons and moved LED
        self.apply_button.pack(side=tk.LEFT, padx=(0,2), expand=True, fill=tk.X)
        self.save_button.pack(side=tk.LEFT, padx=(0,2), expand=True, fill=tk.X)
        self.save_state_led_canvas.pack(side=tk.LEFT, padx=(0, 5)) # Pack LED next to Save
        self.stop_button.pack(side=tk.LEFT, padx=(0,0), expand=True, fill=tk.X)


    def load_data(self, data: dict | None):
        """Populates the entry fields from a data dictionary or sets defaults."""
        if data:
            self.target_voltage_var.set(str(data.get('target_voltage', '')))
            self.duration_var.set(str(data.get('duration', '')))
            self.rate_var.set(str(data.get('rate', '')))

            if data.get('duration') is not None:
                self.ramp_parameter_choice.set("duration")
            elif data.get('rate') is not None:
                self.ramp_parameter_choice.set("rate")
            else:
                self.ramp_parameter_choice.set("duration") # Default

            # If loading data, assume it was previously saved and valid
            self.saved_data = data.copy() # Store a copy
            self.set_save_state_led('green')

        else:
            # Set default/placeholder values if no initial data provided
            self.target_voltage_var.set(f"1.0") # self.target_voltage_var.set(f"{random.uniform(1.0, min(5.0, self.max_voltage)):.1f}")
            self.duration_var.set("")
            self.rate_var.set("0.1") # Clear rate if duration is default
            self.ramp_parameter_choice.set("rate")
            self.saved_data = None # No saved data initially
            self.set_save_state_led('red') # Default to red

        self._update_entry_states()

    def _mark_unsaved(self, *args):
        """Callback function to set the save state LED to red when inputs change."""
        # Only change to red if it's not already red,
        # or if there's no saved data yet.
        if self._save_state_led_state == 'green' or self.saved_data is None:
             self.set_save_state_led('red')

    def _update_entry_states(self):
        """Enables/disables duration/rate entry fields based on radiobutton selection."""
        choice = self.ramp_parameter_choice.get()
        duration_state = tk.DISABLED
        rate_state = tk.DISABLED
        if choice == "duration":
            duration_state = tk.NORMAL
        elif choice == "rate":
            rate_state = tk.NORMAL

        # Only reconfigure if state actually changes to avoid unnecessary trace calls
        if self.duration_entry.cget('state') != duration_state:
            self.duration_entry.config(state=duration_state)
        if self.rate_entry.cget('state') != rate_state:
            self.rate_entry.config(state=rate_state)

        # Mark unsaved when radio button changes state
        # self._mark_unsaved() # Covered by trace on ramp_parameter_choice

    def set_save_state_led(self, state: str):
        """Sets the internal save state LED state and updates its display."""
        if state in ['red', 'green']:
            self._save_state_led_state = state
            self._update_save_state_led_display()

    def get_save_state_led(self) -> str:
        """Returns the current save state LED state ('red' or 'green')."""
        return self._save_state_led_state

    def _update_save_state_led_display(self):
        """Updates the visual appearance of the save state LED."""
        color = COLOR_LED_GREEN if self._save_state_led_state == 'green' else COLOR_LED_RED
        self.save_state_led_canvas.delete("all") # Clear previous drawing
        self.save_state_led_canvas.create_oval(1, 1, LED_SIZE-2, LED_SIZE-2, fill=color, outline=color) # Slightly smaller oval

    def _update_voltage_led_display(self, color: str):
        """Updates the visual appearance of the current voltage LED."""
        self.voltage_led_canvas.delete("all") # Clear previous drawing
        self.voltage_led_canvas.create_oval(1, 1, LED_SIZE-2, LED_SIZE-2, fill=color, outline=color) # Slightly smaller oval

    def _update_current_voltage_display(self, current_v):
        """Periodically fetches and displays the current voltage and updates its LED."""
        led_color = COLOR_LED_OFF
        voltage_str = f"{current_v:.2f} V"
        # Update Voltage LED based on current voltage (Requirement 3)
        if math.isclose(current_v, 0.0, abs_tol=VOLTAGE_ZERO_THRESHOLD):
            led_color = COLOR_LED_RED
        else:
            led_color = COLOR_LED_GREEN
        # Update the label text variable
        self.current_voltage_var.set(voltage_str)
        # Update the voltage LED color
        self._update_voltage_led_display(led_color)


    def _validate_input(self) -> dict | None:
        """
        Validates the current input fields for this channel.
        Returns a dictionary with validated data if successful, None otherwise.
        """
        try:
            target_voltage_str = self.target_voltage_var.get().strip().replace(',', '.')
            if not target_voltage_str:
                raise ValueError("Target voltage must be specified.")
            target_voltage = float(target_voltage_str)

            ramp_choice = self.ramp_parameter_choice.get()
            duration = None
            rate = None

            min_v = 0
            if not (min_v <= target_voltage <= self.max_voltage):
                raise ValueError(f"Target voltage must be between {min_v} and {self.max_voltage} V.")

            if ramp_choice == "duration":
                duration_str = self.duration_var.get().strip().replace(',', '.')
                if not duration_str:
                    raise ValueError("Duration must be specified.")
                duration = float(duration_str)
                if duration <= 0:
                    raise ValueError("Duration must be > 0 seconds.")
            elif ramp_choice == "rate":
                rate_str = self.rate_var.get().strip().replace(',', '.')
                if not rate_str:
                    raise ValueError("Rate must be specified.")
                rate = float(rate_str)
                if rate <= 0:
                    raise ValueError("Rate must be > 0 V/s.")
            else:
                raise ValueError("Invalid ramp parameter choice.")

            # Validation successful
            return {
                'channel_name': self.channel_name,
                'channel_index': self.channel_index,
                'target_voltage': target_voltage,
                'duration': duration,
                'rate': rate
            }

        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Channel {self.channel_name}: {e}", parent=self.master_popup)
            self.set_save_state_led('red') # Validation failed, ensure save state LED is red
            return None
        except Exception as e:
            messagebox.showerror("Error", f"Channel {self.channel_name}: Unexpected validation error: {e}", parent=self.master_popup)
            self.set_save_state_led('red')
            return None

    def _on_save(self):
        """Validates input, saves it internally, and updates save state LED to green."""
        validated_data = self._validate_input()
        if validated_data is not None:
            self.saved_data = validated_data.copy() # Store the validated data
            self.set_save_state_led('green')
            print(f"Channel {self.channel_name}: Settings saved.")
            # Inform the parent popup that data was saved for this channel
            if hasattr(self.master_popup, 'update_saved_data'):
                 self.master_popup.update_saved_data(self.channel_name, self.saved_data)
            else:
                 print(f"Warning: Parent popup does not have 'update_saved_data' method.")


    def _on_apply(self):
        """Validates current input and applies the target voltage via the controller."""
        # Option 1: Use currently entered values (validate first)
        validated_data = self._validate_input()
        if validated_data is None:
            messagebox.showwarning("Apply Failed", f"Channel {self.channel_name}: Invalid settings in fields. Cannot apply.", parent=self.master_popup)
            return # Stop if validation fails

        # Option 2: Use last saved values (if you prefer Apply to only use saved settings)
        # if self.get_save_state_led() == 'red' or not self.saved_data:
        #    messagebox.showwarning("Apply Failed", f"Channel {self.channel_name}: Settings not saved or modified. Save first.", parent=self.master_popup)
        #    return
        # validated_data = self.saved_data # Use saved data

        # --- Proceeding with Option 1 (Apply uses current fields after validation) ---
        if validated_data is not None:
            print(f"Applying Voltage: Chan {validated_data['channel_name']} to {validated_data['target_voltage']}V")
            try:
                # Make sure controller has the method
                if not hasattr(self.controller, 'ramp_voltage_1chan'):
                     raise AttributeError("Controller object missing 'ramp_voltage_1chan' method.")

                self.controller.ramp_voltage_1chan(
                    chan=validated_data['channel_name'],
                    voltage=validated_data['target_voltage'], # Target voltage from input
                    duration=validated_data['duration'],
                    rate=validated_data['rate'],
                    initialise=True # Start the ramp
                )
                self._update_current_voltage_display(validated_data['target_voltage'])
                # Apply does not change the saved state or save state LED color
            except AttributeError as e:
                 messagebox.showerror("Controller Error", f"Channel {self.channel_name}: {e}", parent=self.master_popup)
            except Exception as e:
                messagebox.showerror("Controller Error", f"Channel {self.channel_name}: Error applying voltage: {e}", parent=self.master_popup)
                # If apply fails, should the LED turn red? Maybe not, depends on desired logic.


    def _on_stop(self):
        """Ramps the voltage for this channel down to 0V using saved or default parameters."""
        print(f"Stopping Channel {self.channel_name} (Ramping to 0V)")

        # Use saved parameters if available, otherwise use defaults for the ramp down
        duration = None
        rate = None
        # Prioritize saved parameters if they exist and state is green
        if self.saved_data and self.get_save_state_led() == 'green':
             duration = self.saved_data.get('duration')
             rate = self.saved_data.get('rate')
             print(f"  Using saved params: duration={duration}, rate={rate}")
        else:
             # Fallback: Use currently entered (but potentially unsaved/invalid) values if possible
             temp_validated_data = self._validate_input() # Check current fields silently
             if temp_validated_data:
                 duration = temp_validated_data.get('duration')
                 rate = temp_validated_data.get('rate')
                 print(f"  Using current field values (unsaved/modified): duration={duration}, rate={rate}")
             else:
                # Final fallback if fields are invalid or empty
                duration = 0.5 # Default fast stop duration
                rate = None
                print("  Using default stop duration: 0.5s (saved/current invalid)")

        # Ensure at least one ramp parameter is valid for the call
        if duration is None and rate is None:
             duration = 0.5 # Final fallback
             print("  Neither duration nor rate available, using default duration 0.5s")


        try:
            # Make sure controller has the method
            if not hasattr(self.controller, 'ramp_voltage_1chan'):
                 raise AttributeError("Controller object missing 'ramp_voltage_1chan' method.")

            self.controller.ramp_voltage_1chan(
                chan=self.channel_name,
                voltage=0, # Ramp down to zero
                duration=duration,
                rate=rate)  #, terminate=True) # Ensure channel is closed/terminated after ramp
            
            self._update_current_voltage_display(0)

            # Optionally set target voltage field to 0 after stop?
            # self.target_voltage_var.set("0.0")
            # self._mark_unsaved() # If target voltage is set

        except AttributeError as e:
             messagebox.showerror("Controller Error", f"Channel {self.channel_name}: {e}", parent=self.master_popup)
             # If stop fails, LED state might be uncertain.
        except Exception as e:
            messagebox.showerror("Controller Error", f"Channel {self.channel_name}: Error stopping channel: {e}", parent=self.master_popup)
            # If stop fails, LED state might be uncertain.


    def get_saved_settings(self) -> dict | None:
        """Returns the last successfully saved settings for this channel."""
        return self.saved_data

# --- Example Usage (Requires dummy classes/mocks if run standalone) ---
if __name__ == '__main__':

    # Create dummy/mock classes for testing if needed
    class MockController:
        def __init__(self):
            self._voltages = {} # Store voltage per channel

        def ramp_voltage_1chan(self, chan, voltage, duration, rate, initialise=False, terminate=False):
            print(f"MockController: Ramping {chan} to {voltage}V (duration={duration}, rate={rate}, init={initialise}, term={terminate})")
            # Simulate voltage change
            self._voltages[chan] = voltage
            if terminate:
                 self._voltages[chan] = 0 # Simulate termination sets to 0

        def get_current_voltage(self, chan):
            # Simulate returning current voltage, maybe with some noise
            return self._voltages.get(chan, 0.0) + random.uniform(-0.01, 0.01)

    class MockPopup(tk.Tk): # Use Tk as base for master
        def __init__(self):
            super().__init__()
            self.title("Channel Control Test")
            self.geometry("350x450")
            self._saved_data = {}

        def update_saved_data(self, channel_name, data):
            print(f"MockPopup: Received saved data for {channel_name}: {data}")
            self._saved_data[channel_name] = data

    # --- Run the Test ---
    root = MockPopup()
    mock_controller = MockController()

    # Example initial data (optional)
    initial_c1 = {'target_voltage': 2.5, 'duration': 1.5, 'rate': None}
    initial_c2 = None # Test default values

    frame1 = ChannelControlFrame(root, mock_controller, channel_index=0, channel_name="C1", max_voltage=10.0, initial_data=initial_c1)
    frame1.pack(pady=10, padx=10, fill=tk.X)

    frame2 = ChannelControlFrame(root, mock_controller, channel_index=1, channel_name="C2", max_voltage=5.0, initial_data=initial_c2)
    frame2.pack(pady=10, padx=10, fill=tk.X)

    root.mainloop()