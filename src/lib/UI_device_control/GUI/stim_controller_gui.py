# stimulation_gui.py
from __future__ import annotations # MUST be the first non-comment line

import os
import sys # sys is already imported
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, font
from pathlib import Path # Path is already imported
import typing

# homemade libraries
# This line adds the parent directory of the folder containing stimulation_gui.py to sys.path.
# For example, if stimulation_gui.py is in 'MyProject/lib/GUI/', 'MyProject/lib/' is added to sys.path.
# It's assumed that 'configurable_csv_logger.py' is located in this 'MyProject/lib/' directory.
_logger_parent_directory = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(_logger_parent_directory))

# Attempt to import the ConfigurableCsvLogger
try:
    from configurable_csv_logger import ConfigurableCsvLogger
except ImportError as e:
    print(f"WARNING: Could not import ConfigurableCsvLogger from '{_logger_parent_directory}'. "
          f"GUI status messages will not be logged to a file. Error: {e}")
    ConfigurableCsvLogger = None # Define as None if import fails, for graceful fallback

# Continue with other imports
from lib.UI_device_control.GUI.individual_channel_popup.TargetVoltageSettings_Popup import TargetVoltageSettings_Popup
if typing.TYPE_CHECKING:
    # The sys.path.append for _logger_parent_directory should also cover this,
    # assuming 'lib' is a subdirectory of _logger_parent_directory or _logger_parent_directory is 'lib'
    # sys.path.append(str(Path(__file__).resolve().parent.parent)) # This is _logger_parent_directory
    from lib.UI_device_control.stim_controller_with_gui import StimulationController_withGUI


class ControllerGUI(tk.Frame):
    """
    Tkinter GUI Frame for the Stimulation Controller.
    """
    # Define some colors for status messages
    COLOR_INFO = "black"
    COLOR_WARNING = "orange"
    COLOR_ERROR = "red"
    COLOR_SUCCESS = "green"
    COLOR_RAMP = "blue"
    COLOR_EMERGENCY = "#FF0000" # Bright Red

    def __init__(self, master: tk.Tk, controller: StimulationController_withGUI, log_folder_path=None):
        """
        Initializes the GUI Frame.

        Args:
            master: The root Tkinter window (tk.Tk).
            controller: The StimControllerGUI instance managing the logic.
        """
        super().__init__(master)
        self.master = master
        self.controller = controller
        self.master.title("Stimulation Controller")

        # Define fonts
        self.default_font = font.nametofont("TkDefaultFont")
        self.bold_font = self.default_font.copy()
        self.bold_font.configure(weight="bold")
        self.status_font = self.default_font.copy()
        self.status_font.configure(size=10)
        self.title_font = self.default_font.copy()
        self.title_font.configure(size=12, weight="bold")

        # --- Style for the hide mode switch ---
        style = ttk.Style(self.master)
        style.configure("Switch.TCheckbutton", font=self.default_font)

        # --- Variable for hide mode ---
        self.hide_mode_var = tk.BooleanVar(value=False)


        # Initialize the status logger
        self.status_logger = None
        
        if log_folder_path is None:
            self.log_folder_path = os.path.join(os.getcwd(), "logs") # Default log folder
        else:
            self.log_folder_path = log_folder_path
        self.status_logger = ConfigurableCsvLogger(
            log_folder_path=str(self.log_folder_path),
            filename_prefix="gui_status_messages",
            data_header_columns=['Level', 'Message'] # Timestamp is added automatically by logger
        )
        # This message will go to console, not the GUI status text area yet.
        print(f"INFO: GUI Status Logger initialized. Logging to: {self.log_folder_path}")

        self.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._create_widgets()
        self._initial_widget_state() # This calls update_status, which will now attempt to log

        # Handle window closing
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _create_widgets(self):
        """Creates and arranges all the GUI widgets."""

        # --- Condition Selection ---
        self.condition_frame = ttk.LabelFrame(self, text="1. Select Condition", padding=(15, 5))
        self.condition_frame.pack(fill=tk.X, pady=5)

        self.condition_var = tk.StringVar(value="STIM") # Default selection
        self.stim_radio = ttk.Radiobutton(self.condition_frame, text="STIM", variable=self.condition_var, value="STIM")
        self.sham_radio = ttk.Radiobutton(self.condition_frame, text="SHAM", variable=self.condition_var, value="SHAM")
        self.confirm_condition_button = ttk.Button(self.condition_frame, text="Confirm & Connect", command=self.controller.gui_confirm_condition)#, style="Accent.TButton")

        # --- Hide Mode Switch ---
        self.hide_mode_switch = ttk.Checkbutton(self.condition_frame, text="Hide Mode", 
                                                variable=self.hide_mode_var, onvalue=True, offvalue=False,
                                                command=self.toggle_hide_mode, style="Switch.TCheckbutton")


        self.stim_radio.pack(side=tk.LEFT, padx=5)
        self.sham_radio.pack(side=tk.LEFT, padx=5)
        self.hide_mode_switch.pack(side=tk.LEFT, padx=15)
        self.confirm_condition_button.pack(side=tk.RIGHT, padx=5)

        # --- Voltage Ramp Settings (Grid Layout) ---
        control_frame = ttk.LabelFrame(self, text="2. Control", padding=(10, 5))
        control_frame.pack(fill=tk.X, pady=5)

        self.set_ramp_button = ttk.Button(control_frame, text="Manipulate Individual Voltages", command=self._open_ramp_window)
        self.start_button = ttk.Button(control_frame, text="START Stimulation", command=self.controller.gui_start_stimulation, width=18)
        self.end_button = ttk.Button(control_frame, text="END Stimulation", command=self.controller.gui_end_stimulation, width=18)
        self.beep_button = ttk.Button(control_frame, text="Beep Devices", command=self.controller.gui_beep_devices, width=18)

        self.set_ramp_button.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        self.start_button.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        self.end_button.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")
        self.beep_button.grid(row=1, column=1, padx=5, pady=5, sticky="nsew")

        control_frame.columnconfigure(0, weight=1)
        control_frame.columnconfigure(1, weight=1)
        control_frame.rowconfigure(0, weight=1)
        control_frame.rowconfigure(1, weight=1)

        # --- Status Display ---
        status_frame = ttk.LabelFrame(self, text="Status", padding=(10, 5))
        status_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.status_text = scrolledtext.ScrolledText(status_frame, height=10, wrap=tk.WORD, relief=tk.SUNKEN, borderwidth=1, font=self.status_font)
        self.status_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.status_text.configure(state='disabled') # Read-only

        self.status_text.tag_configure("info", foreground=self.COLOR_INFO)
        self.status_text.tag_configure("warning", foreground=self.COLOR_WARNING, font=self.bold_font)
        self.status_text.tag_configure("error", foreground=self.COLOR_ERROR, font=self.bold_font)
        self.status_text.tag_configure("success", foreground=self.COLOR_SUCCESS, font=self.bold_font)
        self.status_text.tag_configure("ramp", foreground=self.COLOR_RAMP)
        self.status_text.tag_configure("emergency", foreground=self.COLOR_EMERGENCY, font=self.bold_font, background="yellow")

        # --- Quit Button ---
        quit_button = ttk.Button(self, text="Quit Application", command=self.on_closing)
        quit_button.pack(pady=10)

        # --- Styling ---
        if False: # Keep styling block if needed later
            style = ttk.Style()
            try:
                style.configure("Accent.TButton", font=self.bold_font, foreground="white", background="#0078D4")
            except tk.TclError:
                # update_status call might be too early if logger/status_text not fully ready
                # print("Could not apply custom theme.")
                self.master.after(10, lambda: self.update_status("Could not apply custom theme.", "warning"))

    def set_hide_mode(self, hide: bool):
        """
        Programmatically sets the hide mode for the condition variables.

        Args:
            hide (bool): True to turn hide mode ON, False to turn it OFF.
        """
        self.hide_mode_var.set(hide)
        self.toggle_hide_mode()


    def toggle_hide_mode(self):
        """
        Shows or hides the condition radio buttons based on the hide_mode_var state.
        This method is called by the hide_mode_switch.
        """
        if self.hide_mode_var.get():
            # Hide the widgets
            self.stim_radio.pack_forget()
            self.sham_radio.pack_forget()
            self.update_status("Condition selection hidden.", "info")
        else:
            # Show the widgets - they need to be packed again in order
            self.stim_radio.pack(side=tk.LEFT, padx=5)
            self.sham_radio.pack(side=tk.LEFT, padx=5)
            # Ensure the other widgets remain in their place
            self.hide_mode_switch.pack(side=tk.LEFT, padx=15)
            self.confirm_condition_button.pack(side=tk.RIGHT, padx=5)
            self.update_status("Condition selection shown.", "info")

    def _initial_widget_state(self):
        """Sets the initial enabled/disabled state of widgets."""
        self.confirm_condition_button.config(state=tk.NORMAL)
        self.set_widget_state("set_ramp_button", tk.DISABLED)
        self.start_button.config(state=tk.DISABLED)
        self.end_button.config(state=tk.DISABLED)
        self.beep_button.config(state=tk.DISABLED)
        self.update_status("Welcome! Please select condition and confirm.", "info")

    def _open_ramp_window(self):
        """Opens the popup window for setting the voltage ramp."""
        ts_popup = TargetVoltageSettings_Popup(self, self.controller)
        self.wait_variable(ts_popup.finish_triggered)

        self.controller.set_voltages(ts_popup.get_target_voltages())
        ts_popup.destroy()
        self.update_status("Voltage/Ramp settings window closed.", "info")
        self.enable_stimulation_controls(self.controller.stimulation_active)

    def update_status(self, message: str, level: str = "info"):
        """
        Appends a message to the status text area with appropriate color and logs it.
        This method is safe to call from other threads as it schedules the GUI update.
        """
        if not hasattr(self, 'status_text') or not self.status_text.winfo_exists():
            # GUI not fully initialized, log to console only
            print(f"Status Update (GUI not ready): [{level.upper()}] {message}")
            # Optionally, try to log to file here too if self.status_logger is ready
            if self.status_logger:
                try:
                    self.status_logger.log_entry(level, f"(GUI not ready) {message}")
                except Exception as log_ex:
                    print(f"Console Log: Error during early status logging: {log_ex}")
            return
        # Schedule the GUI update and logging to occur in the main Tkinter thread
        self.master.after(0, self._append_status_message, message, level)

    def _append_status_message(self, message: str, level: str):
        """
        Internal method to append message to GUI's ScrolledText and log to CSV.
        This method MUST be called from the main Tkinter thread (e.g., via master.after).
        """
        try:
            # Part 1: Update GUI's ScrolledText
            gui_tag = level.lower()
            if gui_tag not in ["info", "warning", "error", "success", "ramp", "emergency"]:
                gui_tag = "info"  # Default GUI tag
            
            self.status_text.configure(state='normal')
            self.status_text.insert(tk.END, f"{message}\n", gui_tag)
            self.status_text.configure(state='disabled')
            self.status_text.see(tk.END) # Scroll to the end
            # self.master.update_idletasks() # Usually not needed when master.after is used

            # Part 2: Log the message using ConfigurableCsvLogger
            if self.status_logger:
                try:
                    # 'level' is like "info", "warning"; 'message' is the string.
                    self.status_logger.log_entry(level, message)
                except Exception as log_ex:
                    # Avoid crashing the GUI if logging itself fails. Print to console.
                    print(f"ERROR: Failed to write to status log file: {log_ex}")
            
        except tk.TclError as e_gui: # Error related to Tkinter operations
            print(f"ERROR: TclError while updating GUI status text: {e_gui}")
        except Exception as e_unexpected: # Other unexpected errors
            print(f"ERROR: Unexpected error in _append_status_message: {e_unexpected}")

    def set_widget_state(self, widget_name, state):
        """Sets the state (tk.NORMAL or tk.DISABLED) of a specific widget."""
        widget = getattr(self, widget_name, None)
        if widget and isinstance(widget, (ttk.Button, ttk.Entry, ttk.Radiobutton, ttk.Combobox)):
            try:
                widget.config(state=state)
            except tk.TclError: pass # Ignore if widget destroyed
        elif widget_name == "voltage_entries": pass
        elif widget and isinstance(widget, list): pass
        else:
            if hasattr(self, 'status_text') and self.status_text.winfo_exists():
                # Log this type of internal warning too
                self.update_status(f"Internal Warning: Could not find widget '{widget_name}' to set state.", "warning")

    def enable_condition_selection(self):
        self.set_widget_state("confirm_condition_button", tk.NORMAL)

    def disable_condition_selection(self):
        self.set_widget_state("confirm_condition_button", tk.DISABLED)

    def enable_voltage_input(self):
        self.set_widget_state("set_ramp_button", tk.NORMAL)

    def disable_voltage_input(self):
        self.set_widget_state("set_ramp_button", tk.DISABLED)

    def enable_stimulation_controls(self, is_active):
        self.set_widget_state("start_button", tk.DISABLED if is_active else tk.NORMAL)
        self.set_widget_state("end_button", tk.NORMAL) # Original logic: end_button always normal if controls enabled
        self.set_widget_state("beep_button", tk.NORMAL)
        self.enable_voltage_input()

    def disable_all_controls(self):
        self.disable_condition_selection()
        self.disable_voltage_input()
        self.set_widget_state("start_button", tk.DISABLED)
        self.set_widget_state("end_button", tk.DISABLED)
        self.set_widget_state("beep_button", tk.DISABLED)

    def show_emergency_stop_state(self):
        self.update_status("!!! EMERGENCY STOP ACTIVATED !!!", "emergency")
        self.disable_all_controls()
        try: self.master.config(bg=self.COLOR_EMERGENCY)
        except tk.TclError: pass

    def on_closing(self):
        """Handles the window close event."""
        if messagebox.askokcancel("Quit", "Do you want to quit the application?\nStimulation (if active) will be stopped."):
            self.update_status("Application quit requested by user.", "info")
            self.controller.gui_quit()
            # No explicit logger close needed as ConfigurableCsvLogger opens/closes file per write
            # If ConfigurableCsvLogger were to hold resources, self.status_logger.close() would go here.
            self.master.destroy()

if __name__ == '__main__':
    # Example of how to run this GUI (requires a mock controller)
    # This part is for demonstration and testing the GUI standalone

    # Mock for StimulationController_withGUI for testing ControllerGUI
    class MockStimulationController:
        def __init__(self):
            self.stimulation_active = False
            self.gui = None # Will be set by ControllerGUI

        def gui_confirm_condition(self):
            condition = self.gui.condition_var.get()
            self.gui.update_status(f"Condition '{condition}' confirmed & devices (mock) connected.", "success")
            self.gui.disable_condition_selection()
            self.gui.enable_stimulation_controls(self.stimulation_active)

        def gui_start_stimulation(self):
            self.stimulation_active = True
            self.gui.update_status("Stimulation STARTED.", "success")
            self.gui.enable_stimulation_controls(self.stimulation_active)

        def gui_end_stimulation(self):
            self.stimulation_active = False
            self.gui.update_status("Stimulation ENDED.", "info")
            self.gui.enable_stimulation_controls(self.stimulation_active)
            # Typically, you might want to disable voltage input again after ending
            # self.gui.disable_voltage_input()


        def gui_beep_devices(self):
            self.gui.update_status("Beep command sent to devices (mock).", "info")

        def set_voltages(self, voltages):
            self.gui.update_status(f"Target voltages set: {voltages} (mock).", "ramp")
            # Here, one might re-enable start if it was disabled pending voltage settings
            if not self.stimulation_active:
                self.gui.set_widget_state("start_button", tk.NORMAL)


        def gui_quit(self):
            if self.stimulation_active:
                self.gui_end_stimulation() # Ensure stimulation is stopped
            self.gui.update_status("Controller shutting down (mock).", "info")
            print("MockStimulationController: Quit action performed.")
            # Actual application exit is handled by GUI's on_closing destroying master

    root = tk.Tk()
    mock_controller = MockStimulationController()
    app = ControllerGUI(master=root, controller=mock_controller)
    mock_controller.gui = app # Link back the GUI to the mock controller
    
    # Example of using the new method after 2 seconds
    # root.after(2000, lambda: app.set_hide_mode(True))
    # root.after(4000, lambda: app.set_hide_mode(False))


    # Set a minimum size for the window
    root.minsize(450, 550)
    root.mainloop()