# main.py
import sys
import logging
import tkinter as tk
import tkinter.ttk as ttk
import pyvisa
import numpy
import keyboard
# Import the GUI controller instead of the base one
from lib.stim_controller_with_gui import StimulationController_withGUI
from lib.participant_assigner import ParticipantAssigner


import tkinter

# Configure logging for the main script execution (optional for GUI)
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)
# --- Use basic print for critical startup errors before GUI ---

if __name__ == "__main__":
    print("Starting Stimulation Control Application (GUI Mode)")

    # --- I. Set up the participant information and conditions --- #
    # Holder for data received by the callback, if needed after mainloop
    processed_data_holder = [] 
    def my_data_handler_callback(row_data_series):
        print("\n--- Callback: Data Received by Script ---")
        if row_data_series is not None:
            print("Type of received data:", type(row_data_series))
            print("Entire row data (Pandas Series):")
            print(row_data_series.to_string())
            processed_data_holder.append(row_data_series) # Store for potential later use
        else:
            print("No data was successfully processed in this operation, or an error occurred.")
        print("--- Callback: End of Data ---")

    try:
        root = tk.Tk()
        # The ParticipantAssigner will now handle closing 'root' after one operation.
        app = ParticipantAssigner(root, on_data_processed_callback=my_data_handler_callback)
        print("Starting Tkinter mainloop...")
        print("The GUI will perform one operation (assign/load) and then close itself.")
        root.mainloop() # This will run until root.destroy() is called from within the app
    except tk.TclError as e:
        print(f"Tkinter mainloop exited, possibly due to window destruction: ({e})") # Expected
    if processed_data_holder:
        print("\nData captured by callback during the GUI operation:")
        # For simplicity, printing the first (and likely only) item
        print(processed_data_holder[0].to_string()) 

    # --- II. Set up the service controlling the Keysight instruments --- #6
    try:
        # Instantiate the GUI controller
        config_file = 'cfg/keysight_config.json'
        controller = StimulationController_withGUI(config_path=config_file, is_mock_up=True)
        controller.run()
    except ValueError as e:
        print(f"\nConfiguration or Initialization Error: {e}")
        print("Please check your 'config.json' file and device connections.")
        # Show error in a simple Tkinter window if possible
        try:
            root = tk.Tk()
            root.withdraw() # Hide main window
            tk.messagebox.showerror("Initialization Error", f"Configuration or Initialization Error:\n\n{e}\n\nPlease check config.json and connections.")
            root.destroy()
        except Exception:
            pass # Fallback to console print if messagebox fails
        sys.exit(1)
    except Exception as e:
        print(f"\nAn critical error occurred: {e}")
        # Attempt to log exception if logging is configured
        # logger.exception(f"An unexpected critical error occurred: {e}")
        # Show error in a simple Tkinter window if possible
        try:
            root = tk.Tk()
            root.withdraw() # Hide main window
            tk.messagebox.showerror("Critical Error", f"A critical error occurred:\n\n{e}")
            root.destroy()
        except Exception:
             pass # Fallback
        # Note: Cleanup might not run reliably here if controller init failed badly
        sys.exit(1)
    

    print("Stimulation Control Application finished.")