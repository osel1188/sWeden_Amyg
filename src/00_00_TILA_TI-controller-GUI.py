# main.py
import sys
import logging
# Import the GUI controller instead of the base one
from lib.UI_device_control.stim_controller_with_gui import StimulationController_withGUI

# Configure logging for the main script execution (optional for GUI)
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# logger = logging.getLogger(__name__)
# --- Use basic print for critical startup errors before GUI ---

if __name__ == "__main__":
    print("Starting Stimulation Control Application (GUI Mode)")

    # Check for Tkinter availability early
    try:
        import tkinter
        import tkinter.ttk
    except ImportError:
        print("\n--- FATAL ERROR ---")
        print("Tkinter library not found.")
        print("Please ensure Python's Tkinter module is installed on your system.")
        print("(On Debian/Ubuntu: sudo apt-get install python3-tk)")
        print("(On Fedora: sudo dnf install python3-tkinter)")
        print("(On Windows/macOS: Usually included with Python, check installation)")
        print("--------------------\n")
        sys.exit(1)

    # Optional: Check other libraries (already in base controller's check)
    try:
        import pyvisa
        import numpy
        import keyboard
    except ImportError as e:
         print(f"Error: Missing required library: {e}. Please install requirements.")
         print("Try: pip install pyvisa numpy keyboard pyvisa-py")
         sys.exit(1)

    config_file = 'config.json'

    try:
        # Instantiate the GUI controller
        controller = StimulationController_withGUI(config_path=config_file, is_mock_up=False)
        # The run method now starts the Tkinter main loop
        controller.run()

    except ValueError as e:
        print(f"\nConfiguration or Initialization Error: {e}")
        print("Please check your 'config.json' file and device connections.")
        # Show error in a simple Tkinter window if possible
        try:
            root = tkinter.Tk()
            root.withdraw() # Hide main window
            tkinter.messagebox.showerror("Initialization Error", f"Configuration or Initialization Error:\n\n{e}\n\nPlease check config.json and connections.")
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
            root = tkinter.Tk()
            root.withdraw() # Hide main window
            tkinter.messagebox.showerror("Critical Error", f"A critical error occurred:\n\n{e}")
            root.destroy()
        except Exception:
             pass # Fallback
        # Note: Cleanup might not run reliably here if controller init failed badly
        sys.exit(1)
    finally:
        print("Stimulation Control Application finished.")