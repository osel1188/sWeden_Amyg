# ti_cli.py 
#
# Provides an interactive CLI to control the TIManager.
# This file is now a "View" that depends on the TIAPI.
import argparse
import logging
import traceback

# Assuming ti_manager and its dependencies are in the correct Python path
from temporal_interference.ti_manager import TIManager
from temporal_interference.ti_api import TIAPI # Import the new controller layer
from ui.shell_cli import TIShell

def main():
    """
    Main entry point to load config, create all layers, and start the CLI.
    """
    parser = argparse.ArgumentParser(
        description="Interactive CLI for Temporal Interference Manager."
    )
    parser.add_argument(
        '-c', '--config',
        dest='config_path',
        default='config/ti_config.json',
        help='Path to the JSON configuration file (default: config/ti_config.json)'
    )
    args = parser.parse_args()
    
    # Configure basic logging
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')
    
    manager = None # Define manager in outer scope for finally block
    controller = None # Define controller in outer scope for finally block
    try:
        # 1. Initialize the manager (Model)
        logging.info(f"Loading configuration from: {args.config_path}")
        manager = TIManager(config_path=args.config_path)
        manager.connect_all_hardware()

        # 2. Initialize the controller (Controller)
        controller = TIAPI(manager)

        # 3. Start the interactive command loop (View)
        TIShell(controller).cmdloop()

    except FileNotFoundError:
        print(f"Error: Configuration file not found at '{args.config_path}'")
        logging.error(f"Configuration file not found at '{args.config_path}'")
    except KeyError as e:
        print(f"Error: Missing expected key in configuration file: {e}")
        logging.error(f"Missing expected key in configuration file: {e}")
    except ValueError as e:
        print(f"Error: Failed to initialize system: {e}")
        logging.error(f"Failed to initialize system: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during initialization: {e}")
        traceback.print_exc()
        logging.critical(f"An unexpected error occurred: {e}", exc_info=True)
    
    finally:
        # The shutdown logic is now in the controller.
        # do_quit() handles normal exit. This 'finally' block
        # handles crash-based exits.
        if controller:
            print("Ensuring all hardware is disconnected on exit...")
            controller.shutdown()
        elif manager:
            # Fallback if controller failed to init but manager did
            print("Controller not found, calling manager disconnect directly.")
            try:
                manager.disconnect_all_hardware()
            except Exception as e:
                logging.error(f"Error during final hardware disconnection: {e}")


if __name__ == '__main__':
    main()