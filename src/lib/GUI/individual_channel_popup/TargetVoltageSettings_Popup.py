from __future__ import annotations # MUST be the first non-comment line

import tkinter as tk
from tkinter import ttk, messagebox

import os
import sys
from pathlib import Path
import typing
import random # Added for default values


sys.path.append(str(Path(__file__).resolve().parent))
from ChannelControlFrame import ChannelControlFrame

if typing.TYPE_CHECKING:
    # To avoid circular imports during type checking or for IDEs
    # Assume these paths are correctly set up in your project structure
    # sys.path.append(str(Path(__file__).resolve().parent))
    # sys.path.append(str(Path(__file__).resolve().parent.parent))
    try:
        sys.path.append(str(Path(__file__).resolve().parent.parent))
        sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
        from lib.GUI.controller_gui import ControllerGUI
        from lib.stim_controller_with_gui import StimulationController_withGUI
    except ImportError:
        # Define dummy types if imports fail during static analysis
        ControllerGUI = typing.TypeVar('ControllerGUI')
        StimulationController_withGUI = typing.TypeVar('StimulationController_withGUI')


class TargetVoltageSettings_Popup(tk.Toplevel):
    """
    Popup window for setting the target voltage and ramping parameters
    for multiple channels displayed side-by-side.
    """
    def __init__(self, master: ControllerGUI, controller: StimulationController_withGUI):
        """
        Initializes the multi-channel settings popup window.

        Args:
            master: The parent window (ControllerGUI instance).
            controller: The StimControllerGUI instance managing the logic.
        """
        super().__init__(master.master) # Parent should be the Tk root
        self.master_gui = master # ControllerGUI instance
        self.controller = controller

        self.title("Set Channel Voltages/Ramps")
        self.transient(master.master)
        self.grab_set()
        # self.resizable(False, False) # Might need to be resizable horizontally

        # Get channel info
        self.num_channels = self.controller.config['channels']['total']
        self.channel_names = [ch['name'] for ch in self.controller.config['channels']['mapping']]
        self.max_voltage = self.controller.config['safety']['max_voltage_amplitude']

        # Store channel control frame instances
        self.channel_frames: list[ChannelControlFrame] = []

        # Central storage for data saved from channel frames
        # Keys are channel names, values are the saved data dictionaries
        self.all_saved_data: dict[str, dict] = {}

        # Variable to signal closure via Finish button
        self.finish_triggered = tk.BooleanVar(self, value=False)

        self._create_widgets()
        # Load any existing data into the frames? (Assume initial data is passed for now)

        # Center the window (optional, might be large now)
        # self.center_window()

        self.protocol("WM_DELETE_WINDOW", self.hide) # Handle closing with the X button


    def _create_widgets(self):
        """Creates and arranges all the widgets in the popup window."""
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Frame to hold all ChannelControlFrames ---
        channels_area = ttk.Frame(main_frame)
        channels_area.pack(fill=tk.X, expand=True, pady=(0, 15))

        for i in range(self.num_channels):
            channel_name = self.channel_names[i]
            # Pass initial data if available (e.g., from a previous session or defaults)
            # For now, pass None, letting ChannelControlFrame set defaults
            initial_data_for_channel = self.all_saved_data.get(channel_name)

            channel_frame = ChannelControlFrame(
                master=self,
                controller=self.controller,
                channel_index=i,
                channel_name=channel_name,
                max_voltage=self.max_voltage,
                initial_data=initial_data_for_channel # Pass None or preloaded data here
            )
            # Pack frames side by side
            channel_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5, anchor=tk.N)
            self.channel_frames.append(channel_frame)


        # --- Separator ---
        ttk.Separator(main_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)

        # --- Global Button Frame ---
        finish_button_frame = ttk.Frame(main_frame)
        finish_button_frame.pack(fill=tk.X, pady=(5, 0))

        # Finish button - can be used anytime
        self.finish_button = ttk.Button(finish_button_frame, text="Finish Setup", command=self.hide, style="Accent.TButton")
        self.finish_button.pack(side=tk.RIGHT, padx=5) # Position on the right


    def update_saved_data(self, channel_name: str, data: dict):
        """Callback for ChannelControlFrame to update the central storage."""
        self.all_saved_data[channel_name] = data
        print(f"Popup received saved data for {channel_name}: {data}")


    def hide(self):
        """Hides the window without destroying it and releases grab."""
        # No check needed for all LEDs green anymore
        print("Hiding settings window (Finish clicked or window closed).")
        self.grab_release()
        self.withdraw()
        self.finish_triggered.set(True) # Signal that the window was closed


    def show(self):
        """Makes the hidden window visible again and grabs focus."""
        print("Showing settings window.")
        self.deiconify()
        self.grab_set()
        self.lift()
        self.focus_set()
        self.finish_triggered.set(False)
        # Re-load data into frames if necessary, or assume frames retain state
        # For simplicity, assume frames retain their state while hidden.


    def get_target_voltages(self) -> list[float]:
        """
        Returns a list of the *last saved* target voltages for all channels,
        in the order of self.channel_names. Returns 0 if a channel wasn't saved.
        """
        ordered_target_voltages = []
        for name in self.channel_names:
            saved_data = self.all_saved_data.get(name)
            if saved_data and 'target_voltage' in saved_data:
                ordered_target_voltages.append(saved_data['target_voltage'])
            else:
                ordered_target_voltages.append(0.0) # Default to 0 if not saved
        print(f"get_target_voltages returning: {ordered_target_voltages}")
        return ordered_target_voltages

    def get_all_saved_settings(self) -> dict[str, dict]:
        """Returns the dictionary containing all saved settings."""
        return self.all_saved_data.copy()


# Example Usage (requires dummy master and controller for standalone run)
if __name__ == '__main__':

    # --- Create Dummy Classes for Testing ---
    class DummyStimController:
        def __init__(self):
            self.config = {
                'channels': {
                    'total': 4,
                    'mapping': [
                        {'name': 'C1'}, {'name': 'C2'}, {'name': 'C3'}, {'name': 'C4'}
                    ]
                },
                'safety': {
                    'max_voltage_amplitude': 10.0
                }
            }
            self.current_voltages = {name['name']: 0.0 for name in self.config['channels']['mapping']}

        def ramp_voltage_1chan(self, chan, voltage, duration, rate, initialise=False, terminate=False):
            print(f"CONTROLLER: Ramping Chan={chan}, V={voltage}, Dur={duration}, Rate={rate}, Init={initialise}, Term={terminate}")
            # Simulate action
            if initialise:
                print(f"  -> Setting voltage for {chan} to {voltage}")
                self.current_voltages[chan] = voltage
            if terminate:
                 print(f"  -> Terminating/Closing {chan} (voltage set to 0)")
                 self.current_voltages[chan] = 0.0
            import time
            time.sleep(0.1) # Simulate work

    class DummyControllerGUI:
        def __init__(self, root):
            self.master = root # The Tk root window

    # --- Main Application Setup ---
    root = tk.Tk()
    root.title("Main Application Window")

    # Use ttk theme for better styling
    style = ttk.Style()
    try:
        # Optional: Try setting a modern theme like 'clam' or 'alt'
        style.theme_use('clam')
        # Define an accent style for the Finish button (example)
        style.configure("Accent.TButton", foreground="white", background="dodger blue")
    except tk.TclError:
        print("Clam theme not available, using default.")


    dummy_controller = DummyStimController()
    dummy_gui_master = DummyControllerGUI(root)

    # Button to open the popup
    def open_popup():
        popup = TargetVoltageSettings_Popup(dummy_gui_master, dummy_controller)
        root.wait_window(popup) # Wait until the popup is closed

        # After popup closes, check the finish_triggered flag and get data
        if popup.finish_triggered.get():
            print("\nPopup finished.")
            saved_settings = popup.get_all_saved_settings()
            print("All saved settings retrieved:")
            import json
            print(json.dumps(saved_settings, indent=2))

            voltages = popup.get_target_voltages()
            print(f"Ordered target voltages: {voltages}")
        else:
            print("\nPopup closed unexpectedly.")


    open_button = ttk.Button(root, text="Open Channel Settings", command=open_popup)
    open_button.pack(pady=20, padx=20)

    # Hide the main root window initially until popup is dealt with?
    # root.withdraw() # Or manage visibility as needed

    root.mainloop()