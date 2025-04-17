from __future__ import annotations # MUST be the first non-comment line

import tkinter as tk
from tkinter import ttk, messagebox

import os 
import sys
from pathlib import Path
import typing

if typing.TYPE_CHECKING:
    sys.path.append(str(Path(__file__).resolve().parent))
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from controller_gui import ControllerGUI
    from lib.stim_controller_with_gui import StimulationController_withGUI



class TargetVoltageSettings_Popup(tk.Toplevel):
    """
    Popup window for setting the target voltage and ramping parameters
    for individual channels, with validation and status LEDs.
    """
    LED_SIZE = 15 # Size for the LED squares
    COLOR_LED_RED = "red"
    COLOR_LED_GREEN = "lime green" # Brighter green
    COLOR_LED_OFF = "gray" # Or default background color

    def __init__(self, master: ControllerGUI, controller: StimulationController_withGUI):
        """
        Initializes the popup window.

        Args:
            master: The parent window (ControllerGUI instance).
            controller: The StimControllerGUI instance managing the logic.
        """
        super().__init__(master)
        self.master = master # ControllerGUI instance
        self.controller = controller

        self.title("Set Channel Voltage/Ramp")
        self.transient(master.master) # Associate with the main window
        self.grab_set() # Make the window modal
        self.resizable(False, False)

        # Get the number of channels from the controller
        self.num_channels = self.controller.config['channels']['total']
        self.channel_names = [channel_info['name'] for channel_info in self.controller.config['channels']['mapping']]

        # --- Widget Variables ---
        self.selected_channel = tk.StringVar(value=self.channel_names[0])
        self.target_voltage_var = tk.StringVar()
        self.ramp_parameter_choice = tk.StringVar(value="duration") # 'duration' or 'rate'
        self.duration_var = tk.StringVar()
        self.rate_var = tk.StringVar()

        # --- LED State Tracking ---
        self.led_widgets = {} # Dictionary to store LED canvas widgets {channel_index: canvas}
        self.led_states = {i: 'red' for i in range(self.num_channels)} # {channel_index: 'red'/'green'}

        self._create_widgets()
        self._update_entry_states() # Set initial state for duration/rate entries
        self._update_all_led_displays() # Set initial LED colors

        # Center the window (optional)
        self.master.master.update_idletasks()
        master_x = self.master.master.winfo_x()
        master_y = self.master.master.winfo_y()
        master_width = self.master.master.winfo_width()
        master_height = self.master.master.winfo_height()
        self.update_idletasks()
        popup_width = self.winfo_width()
        popup_height = self.winfo_height()
        center_x = master_x + (master_width // 2) - (popup_width // 2)
        center_y = master_y + (master_height // 2) - (popup_height // 2)
        self.geometry(f"+{center_x}+{center_y}")

        self.protocol("WM_DELETE_WINDOW", self.hide) # Handle closing with the X button    
        self.finish_triggered = tk.BooleanVar(self, value=False)
        self.data_saved = []
 

    def _create_widgets(self):
        """Creates and arranges all the widgets in the popup window."""
        main_frame = ttk.Frame(self, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Input Frame ---
        input_frame = ttk.Frame(main_frame)
        input_frame.pack(fill=tk.X, pady=(0, 10))

        # Channel Selection
        ttk.Label(input_frame, text="Channel:").grid(row=0, column=0, padx=(0, 5), pady=5, sticky=tk.W)
        self.channel_combo = ttk.Combobox(input_frame, textvariable=self.selected_channel,
                                          values=self.channel_names, state="readonly", width=8)
        self.channel_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
        # Maybe add a small label to show max voltage here?
        max_v = self.controller.config['safety']['max_voltage_amplitude']
        ttk.Label(input_frame, text=f"(Max: {max_v} V)").grid(row=1, column=2, padx=5, pady=5, sticky=tk.W)


        # Target Voltage
        ttk.Label(input_frame, text="Target Voltage (V):").grid(row=1, column=0, padx=(0, 5), pady=5, sticky=tk.W)
        self.voltage_entry = ttk.Entry(input_frame, textvariable=self.target_voltage_var, width=10)
        self.voltage_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)


        # Ramping Parameters
        ramp_frame = ttk.LabelFrame(input_frame, text="Ramp Parameter", padding=(10, 5))
        ramp_frame.grid(row=2, column=0, columnspan=3, sticky=tk.EW, pady=10)

        duration_radio = ttk.Radiobutton(ramp_frame, text="Duration (s):", variable=self.ramp_parameter_choice,
                                         value="duration", command=self._update_entry_states)
        rate_radio = ttk.Radiobutton(ramp_frame, text="Rate (V/s):", variable=self.ramp_parameter_choice,
                                     value="rate", command=self._update_entry_states)
        self.duration_entry = ttk.Entry(ramp_frame, textvariable=self.duration_var, width=10)
        self.rate_entry = ttk.Entry(ramp_frame, textvariable=self.rate_var, width=10)

        duration_radio.grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.duration_entry.grid(row=0, column=1, padx=5, pady=2)
        rate_radio.grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.rate_entry.grid(row=1, column=1, padx=5, pady=2)

        # --- LED Status Frame ---
        led_frame = ttk.LabelFrame(main_frame, text="Validation Status", padding=(10, 5))
        led_frame.pack(fill=tk.X, pady=5)

        for i in range(self.num_channels):
            channel_name = self.channel_names[i]
            # Frame for each LED + Label
            item_frame = ttk.Frame(led_frame)
            item_frame.pack(side=tk.LEFT, padx=10, pady=5)

            # Use Canvas for a circular/square LED look
            led_canvas = tk.Canvas(item_frame, width=self.LED_SIZE, height=self.LED_SIZE,
                                   borderwidth=1, relief=tk.RAISED, bg=self.cget('bg')) # Match background
            led_canvas.pack(side=tk.LEFT)
            self.led_widgets[i] = led_canvas # Store canvas reference

            ttk.Label(item_frame, text=channel_name).pack(side=tk.LEFT, padx=(5, 0))


        # --- Button Frame ---
        button_frame = ttk.Frame(main_frame, padding=(0, 10, 0, 0))
        button_frame.pack(fill=tk.X)

        self.set_voltage_button = ttk.Button(button_frame, text="Apply Voltage", command=self._on_set_voltage)
        self.save_button = ttk.Button(button_frame, text="Save", command=self._on_save)
        self.finish_button = ttk.Button(button_frame, text="Finish", command=self.hide)#, style="Accent.TButton") # Accent style for Finish

        # Layout buttons (e.g., push to the right)
        button_frame.columnconfigure(0, weight=1) # Spacer
        self.set_voltage_button.pack(side=tk.LEFT, padx=5)
        self.save_button.pack(side=tk.LEFT, padx=5)
        self.finish_button.pack(side=tk.RIGHT, padx=5) # Finish on the right


    def hide(self):
        if all(state == 'green' for state in self.led_states):
            """Hides the window without destroying it and releases grab."""
            print("Hiding settings window.") # For debugging/confirmation
            self.grab_release() # Release modal grab
            self.withdraw()  # Hide the window
            # This change will be detected by wait_variable in the main script
            self.finish_triggered.set(True)


    def show(self):
        """Makes the hidden window visible again and grabs focus."""
        print("Showing settings window.") # For debugging/confirmation
        self.deiconify()
        self.grab_set() # Re-establish modal grab
        self.lift() # Bring window to the front
        self.focus_set() # Set focus to this window
        self.finish_triggered.set(False)

    def _update_entry_states(self):
        """Enables/disables duration/rate entry fields based on radiobutton selection."""
        choice = self.ramp_parameter_choice.get()
        if choice == "duration":
            self.duration_entry.config(state=tk.NORMAL)
            self.rate_entry.config(state=tk.DISABLED)
            self.rate_var.set("") # Clear the inactive field
        elif choice == "rate":
            self.duration_entry.config(state=tk.DISABLED)
            self.rate_entry.config(state=tk.NORMAL)
            self.duration_var.set("") # Clear the inactive field
        else:
            self.duration_entry.config(state=tk.DISABLED)
            self.rate_entry.config(state=tk.DISABLED)

    def _update_led_display(self, channel_index):
        """Updates the visual appearance of a specific LED."""
        if channel_index in self.led_widgets:
            canvas = self.led_widgets[channel_index]
            state = self.led_states.get(channel_index, 'red') # Default to red if state missing
            color = self.COLOR_LED_GREEN if state == 'green' else self.COLOR_LED_RED

            # Draw a filled circle or square on the canvas
            canvas.delete("all") # Clear previous drawing
            canvas.create_oval(2, 2, self.LED_SIZE-1, self.LED_SIZE-1, fill=color, outline=color)
            # Or use create_rectangle for a square LED

    def _update_all_led_displays(self):
        """Updates all LEDs based on their stored states."""
        for i in range(self.num_channels):
            self._update_led_display(i)

    def _validate_input(self):
        """
        Validates the current input fields for the selected channel.
        Returns:
            dict: {'channel_index': int, 'target_voltage': float, 'duration': float|None, 'rate': float|None}
                  if validation is successful.
            None: if validation fails.
        """
        try:
            # Get values
            channel_str = self.selected_channel.get()
            channel_index = int(channel_str[1:]) - 1

            target_voltage_str = self.target_voltage_var.get().strip().replace(',', '.')
            if not target_voltage_str:
                raise ValueError("Target voltage must be specified.")
            target_voltage = float(target_voltage_str)

            ramp_choice = self.ramp_parameter_choice.get()
            duration = None
            rate = None

            # validate voltage range
            max_v = self.controller.config['safety']['max_voltage_amplitude']
            min_v = 0
            if not (min_v <= target_voltage <= max_v):
                raise ValueError(f"Target voltage must be between {min_v} and {max_v} V.")

            # validate ramp parameter
            if ramp_choice == "duration":
                duration_str = self.duration_var.get().strip().replace(',', '.')
                if not duration_str:
                    raise ValueError("Duration must be specified when selected.")
                duration = float(duration_str)
                if duration <= 0:
                    raise ValueError("Duration must be greater than 0 seconds.")
            elif ramp_choice == "rate":
                rate_str = self.rate_var.get().strip().replace(',', '.')
                if not rate_str:
                     raise ValueError("Rate must be specified when selected.")
                rate = float(rate_str)
                if rate <= 0:
                    raise ValueError("Rate must be greater than 0 V/s.")
            else:
                 raise ValueError("Invalid ramp parameter choice.") # Should not happen

            # If all checks pass, return validated data
            return {
                'channel_name': channel_str,
                'channel_index': channel_index,
                'target_voltage': target_voltage,
                'duration': duration,
                'rate': rate
            }

        except ValueError as e:
            messagebox.showerror("Invalid Input", str(e), parent=self)
            return None # Indicate validation failure
        except Exception as e:
             messagebox.showerror("Error", f"An unexpected validation error occurred: {e}", parent=self)
             return None # Indicate validation failure
    
    def _on_save(self):
        """Saves input and updates the corresponding LED if successful."""
        saved_data = self._validate_input()
        if saved_data is not None:
            # Validation successful
            channel_index = saved_data['channel_index']
            if 'B' in saved_data['channel_name']:
                channel_index += 2
            
            self.led_states[channel_index] = 'green'
            self._update_led_display(channel_index)

            # tidy ramp down and close the trigger.
            self.controller.ramp_voltage_1chan(
                chan=saved_data['channel_name'],
                voltage=0,
                duration=saved_data['duration'],
                rate=saved_data['rate'],
                close_after=True
            )
            self.store_saved_data(saved_data)


    def _on_set_voltage(self):
        """Saves input and, if successful, calls the controller to set the voltage."""
        saved_data = self._validate_input()
        if saved_data is not None:
            # Call the controller's method
            self.controller.ramp_voltage_1chan(
                chan=saved_data['channel_name'],
                voltage=saved_data['target_voltage'],
                duration=saved_data['duration'],
                rate=saved_data['rate'],
                initialise=True
            )
            
            # Optional: Provide feedback in the popup
            # print(f"Voltage setting sent for channel {channel_index+1}.")
            # DO NOT close the window (self.destroy() is removed)

    # ----
    # back end functions    
    def store_saved_data(self, saved_data):
        exists = False
        for item in self.data_saved:
            if item.get('channel_name') == saved_data['channel_name'] and item.get('channel_index') == saved_data['channel_index']:
                exists = True
                break
        if not exists:
            self.data_saved.append(saved_data)


    def get_target_voltages(self):
        target_voltages = []
        for channel_name in self.channel_names:
            for saved_item in self.data_saved:
                if saved_item['channel_name'] == channel_name:
                    target_voltages.append(saved_item['target_voltage'])
                    break  # Assuming only one entry per channel name in self.data_saved
        return target_voltages