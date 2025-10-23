# main_gui.py
#
# Main application entry point for the GUI.
# This script loads the Model (TIManager),
# loads the Controller (TIAPI),
# and launches the View (ExperimentWindow).

import sys
import argparse
import logging
import traceback

from PySide6.QtWidgets import QApplication

# Assuming ti_manager, ti_api, and ti_gui are in the correct Python path
from temporal_interference.ti_manager import TIManager
from temporal_interference.ti_api import TIAPI
from ui.main_window import ExperimentWindow  # Import the GUI window

# NEW: Import participant API and related errors
from participant import ParticipantAssignerAPI, ConfigError, RepositoryError


def main():
    """
    Main entry point to load config, create all layers, and start the GUI.
    """
    parser = argparse.ArgumentParser(
        description="GUI for Temporal Interference Manager."
    )
    parser.add_argument(
        '-c', '--config',
        dest='config_path',
        default='config/ti_config.json',
        help='Path to the TI hardware JSON configuration file (default: config/ti_config.json)'
    )
    # NEW: Argument for Participant API config
    parser.add_argument(
        '-p', '--participant-config',
        dest='participant_config_path',
        default='config/participant_config.txt',
        help='Path to the participant API configuration file (default: cfg/api_config.txt)'
    )
    args = parser.parse_args()
    
    # Configure basic logging
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                        handlers=[
                            logging.FileHandler("ti_gui.log"),
                            logging.StreamHandler(sys.stdout)
                        ])
    
    manager = None
    ti_api = None
    participant_api = None
    
    try:
        # 1. Initialize the manager (Model)
        logging.info(f"Loading TI configuration from: {args.config_path}")
        manager = TIManager(config_path=args.config_path)
        manager.connect_all_hardware()
        logging.info("TIManager initialized and hardware connected.")

        # 2. Initialize the controller (Controller)
        ti_api = TIAPI(manager)
        logging.info("TIAPI initialized.")

        # 3. Initialize the Participant API (Logic/Model 2)
        logging.info(f"Loading Participant API configuration from: {args.participant_config_path}")
        participant_api = ParticipantAssignerAPI(args.participant_config_path)
        logging.info("ParticipantAssignerAPI initialized.")

        # 4. Start the Qt Application (View)
        logging.info("Starting PySide6 GUI...")
        app = QApplication(sys.argv)
        
        # Pass BOTH controllers to the main window
        window = ExperimentWindow(
            ti_api=ti_api,
            participant_api=participant_api
        )
        window.show()

        # Start the application event loop
        # sys.exit() ensures the exit code is propagated
        sys.exit(app.exec())

    except FileNotFoundError as e:
        logging.error(f"Configuration file not found: {e}")
        print(f"Error: Configuration file not found: {e}")
    except (KeyError, ValueError) as e:
        logging.error(f"Invalid configuration or system state: {e}")
        print(f"Error: Invalid configuration or system state: {e}")
    # NEW: Catch errors from ParticipantAssignerAPI initialization
    except (ConfigError, RepositoryError) as e:
        logging.error(f"Failed to initialize Participant API: {e}")
        print(f"Error: Failed to initialize Participant API: {e}")
    except Exception as e:
        logging.critical(f"An unexpected error occurred during initialization: {e}", exc_info=True)
        print(f"An unexpected error occurred: {e}")
        traceback.print_exc()
    
    finally:
        # This 'finally' block will execute *after* the GUI has closed
        # and app.exec() has returned.
        # The GUI's closeEvent handles the *normal* shutdown.
        # This block is a fallback for initialization crashes.
        if ti_api:
            logging.info("GUI loop finished.")
            # The closeEvent should have already run shutdown(),
            # but we check just in case.
        elif manager:
            # Fallback if controller failed to init but manager did
            logging.warning("Controller not found, calling manager disconnect directly.")
            try:
                manager.disconnect_all_hardware()
            except Exception as e:
                logging.error(f"Error during final hardware disconnection: {e}")
        
        logging.info("Application terminated.")


if __name__ == '__main__':
    main()