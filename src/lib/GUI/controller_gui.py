# stimulation_gui.py
from __future__ import annotations # MUST be the first non-comment line

import os
import sys
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, font
from pathlib import Path
import typing


# homemade libraries
sys.path.append(str(Path(__file__).resolve().parent.parent))
from GUI.TargetVoltageSettings_Popup import TargetVoltageSettings_Popup
if typing.TYPE_CHECKING:
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from lib.stim_controller_with_gui import StimulationController_withGUI


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

    def __init__(self, master: tk.Tk, controller: StimulationController_withGUI):
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

        self.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self._create_widgets()
        self._initial_widget_state()

        # Handle window closing
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _create_widgets(self):
        """Creates and arranges all the GUI widgets."""

        # --- Condition Selection ---
        condition_frame = ttk.LabelFrame(self, text="1. Select Condition", padding=(10, 5))
        condition_frame.pack(fill=tk.X, pady=5)

        self.condition_var = tk.StringVar(value="STIM") # Default selection
        stim_radio = ttk.Radiobutton(condition_frame, text="STIM", variable=self.condition_var, value="STIM")
        sham_radio = ttk.Radiobutton(condition_frame, text="SHAM", variable=self.condition_var, value="SHAM")
        self.confirm_condition_button = ttk.Button(condition_frame, text="Confirm & Connect", command=self.controller.gui_confirm_condition)#, style="Accent.TButton")

        stim_radio.pack(side=tk.LEFT, padx=5)
        sham_radio.pack(side=tk.LEFT, padx=5)
        self.confirm_condition_button.pack(side=tk.RIGHT, padx=5)

        # --- Voltage Ramp Settings (Button to open popup) ---
        voltage_frame = ttk.LabelFrame(self, text="2. Set Voltage Ramp", padding=(10, 5))
        voltage_frame.pack(fill=tk.X, pady=5)

        self.set_ramp_button = ttk.Button(voltage_frame, text="Set Channel Voltages...", command=self._open_ramp_window)
        self.set_ramp_button.pack(pady=5)

        # --- Main Controls ---
        control_frame = ttk.LabelFrame(self, text="3. Stimulation Control", padding=(10, 5))
        control_frame.pack(fill=tk.X, pady=5)

        self.start_button = ttk.Button(control_frame, text="START Stimulation", command=self.controller.gui_start_stimulation, width=18)
        self.end_button = ttk.Button(control_frame, text="END Stimulation", command=self.controller.gui_end_stimulation, width=18)
        self.beep_button = ttk.Button(control_frame, text="Beep Devices", command=self.controller.gui_beep_devices, width=18)

        self.start_button.pack(side=tk.LEFT, padx=10, pady=5, expand=True)
        self.end_button.pack(side=tk.LEFT, padx=10, pady=5, expand=True)
        self.beep_button.pack(side=tk.LEFT, padx=10, pady=5, expand=True)


        # --- Status Display ---
        status_frame = ttk.LabelFrame(self, text="Status", padding=(10, 5))
        status_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.status_text = scrolledtext.ScrolledText(status_frame, height=10, wrap=tk.WORD, relief=tk.SUNKEN, borderwidth=1, font=self.status_font)
        self.status_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.status_text.configure(state='disabled') # Read-only

        # Configure tags for colored text
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
        if False:
            style = ttk.Style()
            try:
                style.configure("Accent.TButton", font=self.bold_font, foreground="white", background="#0078D4")
            except tk.TclError:
                self.update_status("Could not apply custom theme.", "warning")


    def _initial_widget_state(self):
        """Sets the initial enabled/disabled state of widgets."""
        self.confirm_condition_button.config(state=tk.NORMAL)
        self.set_ramp_button.config(state=tk.DISABLED)
        self.start_button.config(state=tk.DISABLED)
        self.end_button.config(state=tk.DISABLED)
        self.beep_button.config(state=tk.DISABLED)
        self.update_status("Welcome! Please select condition and confirm.", "info")

    def _open_ramp_window(self):
        """Opens the popup window for setting the voltage ramp."""
        # This now blocks until the popup is closed via "Finish" or 'X'
        ts_popup = TargetVoltageSettings_Popup(self, self.controller)
        self.wait_variable(ts_popup.finish_triggered)
        
        self.controller.set_voltages(ts_popup.get_target_voltages())
        # the popup window is destroyed.
        ts_popup.destroy()
        self.update_status("Voltage/Ramp settings window closed.", "info")
        self.enable_stimulation_controls(self.controller.stimulation_active)



    def update_status(self, message, level="info"):
        """Appends a message to the status text area with appropriate color."""
        if not hasattr(self, 'status_text') or not self.status_text.winfo_exists():
            print(f"Status Update Ignored (GUI not ready): {message}")
            return
        self.master.after(0, self._append_status_message, message, level)

    def _append_status_message(self, message, level):
        """Internal method to append message"""
        try:
            tag = level.lower()
            if tag not in ["info", "warning", "error", "success", "ramp", "emergency"]:
                tag = "info"
            self.status_text.configure(state='normal')
            self.status_text.insert(tk.END, f"{message}\n", tag)
            self.status_text.configure(state='disabled')
            self.status_text.see(tk.END)
            self.master.update_idletasks()
        except tk.TclError as e:
            print(f"Error updating GUI status: {e}")
        except Exception as e:
            print(f"Unexpected error updating GUI status: {e}")

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
            # Avoid logging warning if status_text not ready during init
            if hasattr(self, 'status_text') and self.status_text.winfo_exists():
                 self.update_status(f"Warning: Could not find widget '{widget_name}' to set state.", "warning")


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
        self.set_widget_state("end_button", tk.NORMAL if is_active else tk.DISABLED)
        self.set_widget_state("beep_button", tk.NORMAL)

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
            self.controller.gui_quit()

# --- Example Usage (Mock Controller - Updated Slightly) ---
if __name__ == '__main__':
    class MockStimController:
        def __init__(self):
            self.config = {
                'channels': {'total': 4}, # Make sure this matches popup needs
                'safety': {'max_voltage_amplitude': 8.0}
            }
            self.is_connected = False
            self.is_stimulating = False
            self.gui = None
            self.master = None

        def set_gui(self, gui):
            self.gui = gui

        def gui_confirm_condition(self):
            condition = self.gui.condition_var.get()
            self.gui.update_status(f"Attempting connection with condition: {condition}...", "info")
            if self.master:
                self.master.after(1000, self._finish_connection, True, condition)

        def _finish_connection(self, success, condition):
             if success:
                self.is_connected = True
                self.gui.update_status(f"Connected with condition: {condition}.", "success")
                self.gui.disable_condition_selection()
                self.gui.enable_voltage_input()
                self.gui.enable_stimulation_controls(self.is_stimulating)
                self.gui.set_widget_state("beep_button", tk.NORMAL)
             else:
                 self.gui.update_status("Connection failed.", "error")
                 self.gui.enable_condition_selection()

        def gui_start_target_voltage(self, channel_index, target_voltage, duration=None, rate=None):
            # This is called when "Set Voltage" is pressed in the popup
            # (and validation passed)
            if not self.is_connected:
                 self.gui.update_status(f"Cannot set voltage for Ch {channel_index+1}: Not connected.", "error")
                 return
            param_str = f"duration {duration}s" if duration else f"rate {rate} V/s"
            self.gui.update_status(f"COMMAND: Set Ch {channel_index+1} ramp to {target_voltage}V ({param_str}).", "ramp")
            # Add logic to *actually* start the ramp here
            # For simulation, maybe just log it was received.
            # The ramp completion message can be separate if needed.
            # Example: Simulate ramp finish later
            # ramp_time_ms = int((duration * 1000) if duration else (abs(target_voltage - 0) / rate * 1000))
            # if ramp_time_ms <= 0: ramp_time_ms = 50
            # if self.master:
            #     self.master.after(ramp_time_ms, self._ramp_finished, channel_index, target_voltage)

        def _ramp_finished(self, channel_index, final_voltage):
             # Optional: Can be called by actual ramp logic when done
             self.gui.update_status(f"Ramp complete for channel {channel_index+1}. Reached {final_voltage}V.", "success")

        def gui_start_stimulation(self):
            if not self.is_connected:
                 self.gui.update_status("Cannot start stimulation: Not connected.", "error")
                 return
            self.gui.update_status("Starting stimulation...", "info")
            self.is_stimulating = True
            self.gui.enable_stimulation_controls(self.is_stimulating)

        def gui_end_stimulation(self):
            self.gui.update_status("Ending stimulation...", "info")
            self.is_stimulating = False
            self.gui.enable_stimulation_controls(self.is_stimulating)

        def gui_beep_devices(self):
             if not self.is_connected:
                 self.gui.update_status("Cannot beep: Not connected.", "error")
                 return
             self.gui.update_status("Beeping devices...", "info")

        def gui_quit(self):
            self.gui.update_status("Quitting...", "info")
            if self.is_stimulating: self.gui_end_stimulation()
            if self.is_connected:
                 self.gui.update_status("Disconnecting...", "info")
                 self.is_connected = False
            self.gui.update_status("Application closing.", "info")
            if self.master: self.master.after(500, self.master.destroy)

    root = tk.Tk()
    mock_controller = MockStimController()
    mock_controller.master = root
    app = ControllerGUI(master=root, controller=mock_controller)
    mock_controller.set_gui(app)
    root.mainloop()