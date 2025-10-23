# ti_api_modified.py
#
# Central application controller (facade) that manages the TIManager.
# This layer is shared by the CLI and any GUI (e.g., Flask).

import logging
from typing import Optional, Tuple, Any, Dict, List, Set

# Assuming ti_manager and ti_system are accessible
from temporal_interference.ti_manager import TIManager
from temporal_interference.ti_system import TISystemState


class TIAPI:
    """
    Acts as a central controller or facade for the TIManager.
    
    This class contains all the application logic, allowing different
    frontends (like a CLI or a Flask GUI) to use the same
    functionality without duplicating code.
    
    It returns structured data instead of printing to stdout.
    """

    def __init__(self, manager: TIManager):
        self.manager = manager
        logging.info("TIAPI initialized.")

    # --- NEW METHOD ---
    def connect_hardware(self) -> Tuple[bool, str]:
        """
        Connects to all hardware resources (waveform generators).
        Returns: (success, message)
        """
        try:
            self.manager.connect_all_hardware()
            return (True, "All hardware resources connected successfully.")
        except Exception as e:
            logging.error(f"Error during hardware connection: {e}", exc_info=True)
            return (False, f"An unexpected error occurred during hardware connection: {e}")
    # --- END NEW METHOD ---

    def get_system_summary(self) -> Dict[str, Any]:
        """
        Returns a structured summary of the loaded system infrastructure.
        """
        summary = {"systems": {}}
        if not self.manager.ti_systems:
            summary["message"] = "No TI systems were loaded."
            return summary

        for system_key, system in self.manager.ti_systems.items():
            summary["systems"][system_key] = {
                "region": system.region,
                "total_channels": len(system.channels),
                "channels": {
                    channel_key: { "id": channel.channel_id }
                    for channel_key, channel in system.channels.items()
                }
            }
        return summary

    def initialize_protocol(self, protocol_name: str) -> Tuple[bool, str]:
        """
        Initializes a protocol by name.
        Returns: (success, message)
        """
        if not protocol_name:
            return (False, "Error: A protocol name is required.")
        
        try:
            self.manager.initialize_protocol(protocol_name)
            return (True, f"Protocol '{protocol_name}' initialized successfully.")
        except KeyError:
            return (False, f"Error: Protocol '{protocol_name}' not found.")
        except Exception as e:
            logging.error(f"Error during init: {e}", exc_info=True)
            return (False, f"An unexpected error occurred: {e}")

    def start_protocol(self) -> Tuple[bool, str]:
        """
        Starts the currently initialized protocol.
        Returns: (success, message)
        """
        if not self.manager.current_protocol_name:
            return (False, "Error: No protocol initialized. Run 'init <name>' first.")
        
        try:
            self.manager.start_protocol()
            msg = f"Protocol '{self.manager.current_protocol_name}' start command issued."
            return (True, msg)
        except Exception as e:
            logging.error(f"Error during start: {e}", exc_info=True)
            return (False, f"An unexpected error occurred: {e}")

    def stop_protocol(self) -> Tuple[bool, str]:
        """
        Stops all systems gracefully.
        Returns: (success, message)
        """
        try:
            self.manager.stop_protocol()
            return (True, "Protocol stop command issued (ramp-down initiated).")
        except Exception as e:
            logging.error(f"Error during stop: {e}", exc_info=True)
            return (False, f"An unexpected error occurred: {e}")

    def emergency_stop(self) -> Tuple[bool, str]:
        """
        Triggers an immediate emergency stop on all systems.
        Returns: (success, message)
        """
        try:
            self.manager.emergency_stop_all_systems()
            return (True, "Emergency stop command issued to all systems.")
        except Exception as e:
            logging.error(f"Error during estop: {e}", exc_info=True)
            return (False, f"An unexpected error occurred: {e}")

    def get_status(self) -> Tuple[bool, Any]:
        """
        Retrieves detailed status for all channels.
        Returns: (success, data_or_message)
        """
        try:
            info = self.manager.get_all_channel_info()
            return (True, info)
        except Exception as e:
            logging.error(f"Error getting status: {e}", exc_info=True)
            return (False, f"An unexpected error occurred: {e}")

    # --- MODIFICATION: NEW DIGESTIBLE GETTERS ---

    def get_overall_status(self) -> Tuple[bool, str]:
        """
        Gets a single, high-level aggregated status for all systems.
        Possible return values: IDLE, ERROR, MIXED, or a specific
        TISystemState name if all systems are in that state.
        
        Returns: (success, status_string)
        """
        try:
            systems = self.manager.ti_systems.values()
            if not systems:
                return (True, "IDLE")

            unique_states: Set[TISystemState] = {s.state for s in systems}
            
            if TISystemState.ERROR in unique_states:
                return (True, "ERROR")
            
            if len(unique_states) > 1:
                return (True, "MIXED")
            
            # All systems are in the same state
            return (True, unique_states.pop().name)

        except Exception as e:
            logging.error(f"Error getting overall status: {e}", exc_info=True)
            return (False, f"An unexpected error occurred: {e}")

    def get_system_states(self) -> Tuple[bool, Dict[str, str]]:
        """
        Gets a simple dictionary mapping system keys to their current state name.
        
        Example: {"ti_A": "RUNNING_AT_TARGET", "ti_B": "IDLE"}
        
        Returns: (success, state_map_or_message)
        """
        try:
            state_map = {
                key: system.state.name
                for key, system in self.manager.ti_systems.items()
            }
            return (True, state_map)
        except Exception as e:
            logging.error(f"Error getting system states: {e}", exc_info=True)
            return (False, f"An unexpected error occurred: {e}")

    def get_all_current_voltages(self) -> Tuple[bool, Dict[str, Dict[str, float]]]:
        """
        Gets a nested dictionary of current voltages for all channels.
        
        Example: {"ti_A": {"A1": 1.5, "A2": 1.5}, "ti_B": {"B1": 0.0}}
        
        Returns: (success, voltage_map_or_message)
        """
        try:
            voltage_map: Dict[str, Dict[str, float]] = {}
            for system_key, system in self.manager.ti_systems.items():
                voltage_map[system_key] = {
                    channel_key: channel.get_current_voltage()
                    for channel_key, channel in system.channels.items()
                }
            return (True, voltage_map)
        except Exception as e:
            logging.error(f"Error getting current voltages: {e}", exc_info=True)
            return (False, f"An unexpected error occurred: {e}")

    # --- END OF NEW METHODS ---

    def ramp_single_channel(self, system_key: str, channel_key: str, 
                            target_voltage: float, 
                            rate_v_per_s: Optional[float] = None) -> Tuple[bool, str]:
        """
        Ramps a *single* channel to a new voltage.
        This method is NON-BLOCKING. Use 'wait_for_ramps' to wait.
        Returns: (success, message)
        """
        try:
            kwargs = {}
            if rate_v_per_s is not None:
                kwargs['rate_v_per_s'] = rate_v_per_s
                rate_msg = f"at {rate_v_per_s} V/s"
            else:
                rate_msg = "at default rate"

            self.manager.ramp_single_channel(
                system_key=system_key,
                channel_key=channel_key,
                target_voltage=target_voltage,
                **kwargs
            )
            msg = f"Ramp initiated for '{system_key}/{channel_key}' to {target_voltage}V {rate_msg}."
            return (True, msg)
            
        except KeyError:
            return (False, f"Error: System '{system_key}' or Channel '{system_key}' not found.")
        except Exception as e:
            logging.error(f"Error during ramp: {e}", exc_info=True)
            return (False, f"An unexpected error occurred: {e}")

    def set_channel_target_voltage(self, system_key: str, channel_key: str, 
                                   target_voltage: float) -> Tuple[bool, str]:
        """
        Sets a channel's target voltage parameter *before* a protocol is started.
        Returns: (success, message)
        """
        try:
            self.manager.set_channel_target_voltage(
                system_key=system_key,
                channel_key=channel_key,
                target_voltage=target_voltage
            )
            msg = f"Target voltage for '{system_key}/{channel_key}' set to {target_voltage}V."
            return (True, msg)
        except KeyError:
            return (False, f"Error: System '{system_key}' or Channel '{channel_key}' not found.")
        except Exception as e:
            logging.error(f"Error in set_target_v: {e}", exc_info=True)
            return (False, f"An unexpected error occurred: {e}")

    # --- NEW METHOD AS REQUESTED ---
    def get_channel_target_voltage(self, system_key: str, channel_key: str) -> Tuple[bool, Any]:
        """
        Gets the configured target voltage parameter for a single channel.
        Returns: (success, voltage_or_message)
        """
        try:
            # get_system raises KeyError if system_key is bad
            system = self.manager.get_system(system_key)
            
            # system.channels[...] raises KeyError if channel_key is bad
            voltage = system.channels[channel_key].target_voltage
            
            return (True, voltage)
            
        except KeyError:
            return (False, f"Error: System '{system_key}' or Channel '{channel_key}' not found.")
        except Exception as e:
            logging.error(f"Error in get_target_v: {e}", exc_info=True)
            return (False, f"An unexpected error occurred: {e}")
    # --- END NEW METHOD ---

    def wait_for_ramps(self, timeout_s: Optional[float] = None) -> Tuple[bool, str]:
        """
        Blocks until all system ramps are finished.
        Returns: (success, message)
        """
        try:
            success = self.manager.wait_for_all_ramps_to_finish(timeout_s=timeout_s)
            if success:
                return (True, "All ramps completed.")
            else:
                return (False, "Wait timed out before all ramps completed.")
        except Exception as e:
            logging.error(f"Error while waiting for ramps: {e}", exc_info=True)
            return (False, f"An unexpected error occurred while waiting: {e}")

    def check_state(self, state_name: str) -> Tuple[bool, Any]:
        """
        Checks if all systems are in the specified state.
        Returns: (success, data_or_message)
        """
        state_name = state_name.strip().upper()
        if not state_name:
            return (False, "Error: A state name is required.")
        
        try:
            target_state = TISystemState[state_name]
            result = self.manager.check_all_systems_state(target_state)
            return (True, result)
        except KeyError:
            valid_states = ", ".join([s.name for s in TISystemState])
            return (False, f"Error: Invalid state '{state_name}'. Valid states are: {valid_states}")
        except Exception as e:
            logging.error(f"Error checking state: {e}", exc_info=True)
            return (False, f"An unexpected error occurred: {e}")

    def shutdown(self) -> Tuple[bool, str]:
        """
        Performs a graceful shutdown and disconnects hardware.
        Returns: (success, message)
        """
        try:
            # Check if already idle
            is_idle = self.manager.check_all_systems_state(TISystemState.IDLE)
            
            if not is_idle:
                logging.warning("Systems not IDLE. Issuing graceful stop...")
                self.manager.stop_protocol()
                self.manager.wait_for_all_ramps_to_finish(timeout_s=10.0)
            
            logging.info("Disconnecting all hardware...")
            self.manager.disconnect_all_hardware()
            return (True, "Shutdown complete. All hardware disconnected.")
        except Exception as e:
            logging.error(f"Error during shutdown: {e}", exc_info=True)
            return (False, f"An error occurred during hardware disconnection: {e}")