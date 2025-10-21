# ti_manager.py

from typing import List, Dict, Any
import logging

from .ti_config import TIConfig
from .ti_system import TISystem

class TIManager:
    """
    Manages all TI systems for the experiment by loading and interpreting
    a configuration file. Each TI system corresponds to a target region
    and contains two pairs of electrodes.
    
    This class is responsible for applying protocol settings (voltages, 
    frequencies) to the TISystem objects and controlling their
    lifecycle (run, stop, emergency_stop).
    """
    def __init__(self, config_path: str = 'ti_config.json'):
        """
        Initializes the TIManager.

        Args:
            config_path (str): The path to the JSON configuration file.
        """
        self.config_handler: TIConfig = TIConfig(config_path)
        
        # The TIManager requests the system list from the config handler, which acts as a factory.
        self.ti_systems: Dict[str, TISystem] = self.config_handler.get_ti_systems()
        self.protocols: Dict[str, Any] = self.config_handler.get_protocols()
        
        self.current_protocol: Dict[str, Any] | None = None
        
        logging.info(f"TIManager initialized with {len(self.ti_systems)} TI systems from config.")
        for system_key in self.ti_systems:
            logging.info(f"  -> Found system: '{system_key}' targeting '{self.ti_systems[system_key].region}'")

    def add_system(self, system: TISystem, system_key: str) -> None:
        """Adds a pre-configured TI system to the manager."""
        if system_key in self.ti_systems:
            logging.warning(f"Overwriting existing system with key '{system_key}'.")
        self.ti_systems[system_key] = system

    def get_system(self, system_key: str) -> TISystem:
        """
        Retrieves a specific TI system by its key (e.g., 'ti_A').

        Args:
            system_key (str): The key of the system to retrieve.

        Returns:
            TISystem: The requested TISystem object.
        
        Raises:
            KeyError: If the system_key is not found.
        """
        try:
            return self.ti_systems[system_key]
        except KeyError:
            logging.error(f"TI system key '{system_key}' not found.")
            raise

    def set_protocol(self, protocol_name: str) -> None:
        """
        Sets a named protocol to all managed TI systems.
        This configures the target frequencies and voltages for each system
        based on the protocol definition.
        
        Args:
            protocol_name (str): The name of the protocol (e.g., "STIM", "SHAM").
            
        Raises:
            KeyError: If the protocol_name or a required setting is not found.
        """
        if protocol_name not in self.protocols:
            logging.error(f"Protocol '{protocol_name}' not found in configuration.")
            raise KeyError(f"Protocol '{protocol_name}' not found.")
            
        self.current_protocol = self.protocols[protocol_name]
        logging.info(f"Applying protocol '{protocol_name}': {self.current_protocol.get('description', 'No description')}")

        try:
            # Iterate over each system managed by this manager (e.g., "ti_A", "ti_B")
            for system_key, system in self.ti_systems.items():
                if system_key not in self.current_protocol:
                    logging.warning(f"Protocol '{protocol_name}' has no settings for system '{system_key}'. Skipping.")
                    continue
                
                protocol_settings = self.current_protocol[system_key]
                channel_settings_list = protocol_settings.get('channel_settings', [])
                
                if len(channel_settings_list) != 2:
                    logging.error(f"Protocol error: System '{system_key}' must have exactly 2 channel_settings. Found {len(channel_settings_list)}.")
                    continue
                
                # Create a map for robust channel lookup (e.g., "A1" -> {...settings...})
                settings_map = {s['channel']: s for s in channel_settings_list}

                # Get the channel IDs from the system's electrode pairs
                # system.electrode_pairs is guaranteed to have 2 elements by TISystem __init__
                pair1_id = system.electrode_pairs[0].channel_id
                pair2_id = system.electrode_pairs[1].channel_id

                if pair1_id not in settings_map or pair2_id not in settings_map:
                    logging.error(f"Protocol mismatch: Could not find settings for channels '{pair1_id}' and '{pair2_id}' in protocol for system '{system_key}'.")
                    continue

                # Extract settings using the channel IDs
                settings1 = settings_map[pair1_id]
                settings2 = settings_map[pair2_id]
                
                freq1 = settings1['frequency_hz']
                volt1 = settings1['target_voltage_V']
                
                freq2 = settings2['frequency_hz']
                volt2 = settings2['target_voltage_V']
                
                # Apply settings to the TISystem object
                system.setup_frequencies(freq1, freq2)
                system.setup_target_voltage(volt1, volt2)
                
            logging.info(f"Successfully applied protocol '{protocol_name}' to all configured systems.")

        except KeyError as e:
            logging.error(f"Failed to apply protocol '{protocol_name}': Missing key {e}", exc_info=True)
            self.current_protocol = None # Invalidate protocol on error
            raise
        except Exception as e:
            logging.error(f"An unexpected error occurred applying protocol '{protocol_name}': {e}", exc_info=True)
            self.current_protocol = None # Invalidate protocol on error
            raise

    def run_all_systems(self) -> None:
        """
        Runs all managed TI systems based on the currently applied protocol.
        This will initiate the voltage ramp-up to the target voltages.
        """
        if not self.current_protocol:
            logging.error("Cannot run systems: No protocol has been applied.")
            return

        logging.info("--- RUNNING ALL SYSTEMS ---")
        for system_key, system in self.ti_systems.items():
            if system_key not in self.current_protocol:
                logging.warning(f"Skipping run for '{system_key}': Not defined in current protocol.")
                continue
            
            try:
                # Get ramp duration from the first channel's settings
                # (Assumption: ramp time is the same for both channels in a system)
                settings = self.current_protocol[system_key]['channel_settings'][0]
                ramp_duration = settings['ramp_duration_s']
                
                logging.info(f"Starting system '{system_key}' with {ramp_duration}s ramp...")
                system.run(ramp_duration_sec=ramp_duration)
                
            except (KeyError, IndexError, TypeError) as e:
                logging.error(f"Failed to get ramp duration for system '{system_key}': {e}. Skipping run.")
            except Exception as e:
                logging.error(f"An unexpected error occurred while running system '{system_key}': {e}", exc_info=True)
                system.emergency_stop() # Ensure safety

    def stop_all_systems(self, default_ramp_sec: float = 1.0) -> None:
        """
        Stops all managed TI systems by ramping down voltage to zero.
        
        Attempts to use the ramp duration from the applied protocol.
        If no protocol is set, uses the provided default.
        
        Args:
            default_ramp_sec (float): Ramp-down time if no protocol is applied.
        """
        logging.info("--- STOPPING ALL SYSTEMS ---")
        for system_key, system in self.ti_systems.items():
            ramp_duration = default_ramp_sec
            
            # Try to get ramp time from protocol
            if self.current_protocol and system_key in self.current_protocol:
                try:
                    settings = self.current_protocol[system_key]['channel_settings'][0]
                    ramp_duration = settings['ramp_duration_s']
                except (KeyError, IndexError, TypeError):
                    logging.warning(f"Could not find ramp time for '{system_key}' in protocol. Using default {default_ramp_sec}s.")
            else:
                 logging.info(f"No protocol applied. Using default ramp time {default_ramp_sec}s for '{system_key}'.")
            
            try:
                logging.info(f"Stopping system '{system_key}' with {ramp_duration}s ramp...")
                system.stop(ramp_duration_sec=ramp_duration)
            except Exception as e:
                logging.error(f"An unexpected error occurred while stopping system '{system_key}': {e}", exc_info=True)
                system.emergency_stop() # Ensure safety

    def emergency_stop_all_systems(self) -> None:
        """
        Triggers an immediate, no-ramp emergency stop on all managed systems.
        """
        logging.critical("--- EMERGENCY STOP TRIGGERED FOR ALL SYSTEMS ---")
        for system_key, system in self.ti_systems.items():
            try:
                system.emergency_stop()
            except Exception as e:
                logging.error(f"An error occurred during emergency stop for system '{system_key}': {e}", exc_info=True)