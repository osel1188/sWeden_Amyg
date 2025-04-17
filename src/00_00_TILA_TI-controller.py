# main.py
import sys
import logging

from lib.stim_controller import StimulationController

# Configure logging for the main script execution
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting Stimulation Control Application")

    # Ensure necessary libraries are installed (optional check)
    try:
        import pyvisa
        import numpy
        import keyboard
    except ImportError as e:
         logger.error(f"Missing required library: {e}. Please install requirements.")
         logger.error("Try: pip install pyvisa numpy keyboard pyvisa-py") # pyvisa-py might be needed depending on backend
         sys.exit(1)


    config_file = 'config.json' # Or get from command line arguments

    try:
        controller = StimulationController(config_path=config_file)
        controller.run() # Start the main application logic

    except ValueError as e:
        logger.error(f"Configuration or Initialization Error: {e}")
        print(f"\nError: {e}")
        print("Please check your 'config.json' file and device connections.")
        sys.exit(1)
    except Exception as e:
        # Catch unexpected errors during initialization or run
        logger.exception(f"An unexpected critical error occurred: {e}") # Log traceback
        print(f"\nAn critical error occurred: {e}")
        # Attempt cleanup if controller object exists, otherwise just exit
        if 'controller' in locals() and controller is not None:
            try:
                print("Attempting emergency cleanup...")
                controller.cleanup()
            except Exception as cleanup_err:
                 logger.error(f"Error during final cleanup attempt: {cleanup_err}")
        sys.exit(1)
    finally:
        logger.info("Stimulation Control Application finished.")