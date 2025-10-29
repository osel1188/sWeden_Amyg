# ti_manager.py (MODIFIED)

from typing import List, Dict, Any, Optional
import logging
from ..config import TIConfig
from ..core.system import TISystem, TISystemHardwareState
from ..hardware.hardware_manager import HardwareManager
from .system_monitor import SystemMonitor
# from .async_stop_handler import AsyncStopHandler # MODIFIED: Removed
from .trigger_manager import TriggerManager

logger = logging.getLogger(__name__)

class TIManager:
    """
    Manages all TI systems for the experiment by loading and interpreting
    a configuration file. Each TI system corresponds to a target region
    and contains one or more TIChannels.
    
    This class is responsible for applying protocol settings (voltages, 
    frequencies) to the TISystem objects and controlling their
    lifecycle (run, stop, emergency_stop).
    
    It delegates hardware-specific logic (connect/disconnect, enable/disable)
    and state monitoring (polling, waiting) to dedicated service classes.
    """
    def __init__(self, config_path: str = 'ti_config.json'):
        """
        Initializes the TIManager and its subordinate services.

        Args:
            config_path (str): The path to the JSON configuration file.
        """
        self.config_handler: TIConfig = TIConfig(config_path)
        
        self.protocols: Dict[str, Any] = self.config_handler.get_protocols()
        
        self.ti_systems: Dict[str, TISystem] = self.config_handler.get_ti_systems()
        if not self.ti_systems:
                logger.warning("TIConfig returned no TI systems.")
        else:
            logger.info(f"Loaded {len(self.ti_systems)} TI system(s) from config.")
        
        self.current_protocol_name: str | None = None
        
        self.monitor = SystemMonitor(self.ti_systems)

        self.state_monitor = TriggerManager(
            self.monitor, 
            self._find_hw_manager(),
            poll_interval_s=0.1, 
            idle_debounce_s=10.0
        )
        self.state_monitor.start_monitoring()
        
        logger.info(f"TIManager initialized with {len(self.ti_systems)} TI systems from config.")
        for system_key in self.ti_systems:
            logger.info(f"  -> Found system: '{system_key}' targeting '{self.ti_systems[system_key].region}'")

    # --- NEW: HardwareManager Accessor and Delegator Methods ---

    def _find_hw_manager(self) -> Optional[HardwareManager]:
        """
        Retrieves the shared HardwareManager instance from the first
        available channel.
        
        This relies on TIConfig injecting the *same* hw_manager
        instance into all TIChannel objects.
        """
        if not self.ti_systems:
            logger.warning("_find_hw_manager: No TI systems loaded.")
            return None
        
        first_system = next(iter(self.ti_systems.values()))
        first_channel = next(iter(first_system.channels.values()))
        return first_channel.hw_manager

    # --- End Hardware Delegator Methods ---

    def connect_all_hardware(self) -> None:
        """
        Connects to all unique hardware resources by delegating
        to the HardwareManager, accessed via a TISystem.
        """
        for system in self.ti_systems.values():
            system.connect_all()

    def disconnect_all_hardware(self) -> None:
        """
        Disconnects from all unique hardware resources by delegating
        to the HardwareManager, accessed via a TISystem.
        """
        for system in self.ti_systems.values():
            system.disconnect_all()

    def get_system(self, system_key: str) -> TISystem:
        try:
            return self.ti_systems[system_key]
        except KeyError:
            logger.error(f"TI system key '{system_key}' not found.")
            raise

    def initialize_protocol(self, protocol_name: str) -> None:
        if protocol_name not in self.protocols:
            logger.error(f"Protocol '{protocol_name}' not found in configuration.")
            raise KeyError(f"Protocol '{protocol_name}' not found.")
            
        protocol_data = self.protocols[protocol_name]
        self.current_protocol_name = protocol_name
        
        logger.info(f"Initializing protocol '{protocol_name}': {protocol_data.get('description', 'No description')}")

        try:
            # Iterate over each managed system (e.g., "ti_A", "ti_B")
            for system_key, system in self.ti_systems.items():
                if system_key not in protocol_data:
                    logger.warning(f"Protocol '{protocol_name}' has no settings for system '{system_key}'. Skipping.")
                    continue
                
                protocol_settings = protocol_data[system_key]
                channel_settings_list = protocol_settings.get('channel_settings', [])
                
                if not channel_settings_list:
                    logger.error(f"Protocol error: System '{system_key}' has no 'channel_settings' defined.")
                    continue
                
                # Build dictionaries for the TISystem's N-channel API
                target_voltages: Dict[str, float] = {}
                target_frequencies: Dict[str, float] = {}
                ramp_durations: Dict[str, float] = {}

                for settings in channel_settings_list:
                    channel_key = settings['channel']
                    
                    # Validate that the channel from the protocol exists in the system
                    if channel_key not in system.channels:
                        logger.error(f"Protocol mismatch: Channel '{channel_key}' (for system '{system_key}') not found in hardware config. Skipping channel.")
                        continue
                    
                    target_voltages[channel_key] = settings['target_voltage_V']
                    target_frequencies[channel_key] = settings['frequency_hz']
                    ramp_durations[channel_key] = settings['ramp_duration_s']
                
                # Apply settings to the TISystem object
                system.setup_target_voltage(target_voltages)
                system.set_frequencies(target_frequencies)
                system.set_ramp_durations(ramp_durations)
                
            logger.info(f"Successfully initialized protocol '{protocol_name}' for all configured systems.")

        except KeyError as e:
            logger.error(f"Failed to apply protocol '{protocol_name}': Missing key {e}", exc_info=True)
            self.current_protocol_name = None # Invalidate protocol on error
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred applying protocol '{protocol_name}': {e}", exc_info=True)
            self.current_protocol_name = None # Invalidate protocol on error
            raise

    def set_channel_target_voltage(self,
                                   system_key: str,
                                   channel_key: str,
                                   target_voltage: float) -> None:
        """
        Sets the target voltage parameter for a *single* channel in a
        specific system. This does *not* initiate a ramp.
        
        This is for programmatically overriding a protocol setting 
        *before* 'start_protocol' is called. To ramp a running channel
        to a new voltage, use 'ramp_single_channel' instead.

        Args:
            system_key (str): The key of the system (e.g., 'ti_A').
            channel_key (str): The key of the channel (e.g., 'A1').
            target_voltage (float): The target voltage (V) to set.
        """
        try:
            system = self.get_system(system_key)
            # TISystem.setup_target_voltage accepts a dict.
            system.setup_target_voltage({channel_key: target_voltage})
            logger.info(f"Set target voltage parameter for '{system_key}/{channel_key}' to {target_voltage}V.")
        except KeyError:
            logger.error(f"Cannot set voltage parameter: System '{system_key}' not found.")
        except Exception as e:
            logger.error(f"Error setting target voltage for '{system_key}/{channel_key}': {e}", exc_info=True)

    def start_protocol(self) -> None:
        """
        Starts all managed TI systems based on the currently
        initialized protocol. This initiates the non-blocking
        voltage ramp-up for all systems.
        
        The TriggerManager will detect the resulting
        IDLE -> RUNNING state change and enable hardware.
        """
        if not self.current_protocol_name:
            logger.error("Cannot start protocol: No protocol has been initialized. Call initialize_protocol() first.")
            return

        logger.info(f"--- STARTING PROTOCOL: {self.current_protocol_name} ---")
        protocol_data = self.protocols[self.current_protocol_name]
        
        for system_key, system in self.ti_systems.items():
            if system_key not in protocol_data:
                logger.warning(f"Skipping start for '{system_key}': Not defined in current protocol.")
                continue
            
            try:
                logger.info(f"Starting system '{system_key}' (targeting {system.region})...")
                # TISystem.start() is parameter-less and non-blocking
                # This will trigger the state change.
                system.start()
                
            except Exception as e:
                logger.error(f"An unexpected error occurred while starting system '{system_key}': {e}", exc_info=True)
                system.emergency_stop() # Ensure safety

    def stop_protocol(self) -> None:
        """
        Stops all managed TI systems by initiating a non-blocking ramp
        down to zero.
        
        The TriggerManager will detect the resulting
        RUNNING -> IDLE state change and secure hardware
        after its debounce period.
        """
        logger.info("--- STOPPING ALL SYSTEMS (Graceful ramp-down) ---")
        for system_key, system in self.ti_systems.items():
            try:
                logger.info(f"Stopping system '{system_key}'...")
                # TISystem.stop() is parameter-less and non-blocking
                # This will eventually trigger the state change to IDLE.
                system.stop()
            except Exception as e:
                logger.error(f"An unexpected error occurred while stopping system '{system_key}': {e}", exc_info=True)
                system.emergency_stop() # Ensure safety        
        
    def get_all_channel_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Retrieves detailed state information for all channels in all systems
        by delegating to the SystemMonitor.

        Returns:
            Dict[str, Dict[str, Any]]: A nested dictionary:
            {
                "system_key": {
                    "channel_key": { ...info... }
                }
            }
        """
        return self.monitor.get_all_channel_info()

    def check_all_systems_state(self, target_state: TISystemHardwareState) -> bool:
        """
        Checks if all managed TI systems are in the specified state
        by delegating to the SystemMonitor.

        Args:
            target_state (TISystemHardwareState): The state to check for.

        Returns:
            bool: True if all systems are in the target state, False otherwise.
        """
        return self.monitor.check_all_systems_state(target_state)

    def wait_for_all_ramps_to_finish(self, poll_interval_s: float = 0.05, timeout_s: Optional[float] = None) -> bool:
        """
        Blocks the calling thread until all managed TISystem instances
        are no longer ramping, by delegating to the SystemMonitor.

        Args:
            poll_interval_s (float): The time to wait between checks.
            timeout_s (float | None): Maximum time to wait. If None,
                                      waits indefinitely.

        Returns:
            bool: True if all ramps finished, False if the wait timed out.
        """
        try:
            return self.monitor.wait_for_all_ramps_to_finish(poll_interval_s, timeout_s)
        except KeyboardInterrupt:
            logger.warning("Wait for ramps interrupted by user (KeyboardInterrupt).")
            self.emergency_stop_all_systems()
            return False

    def ramp_single_channel(self, 
                            system_key: str, 
                            channel_key: str, 
                            target_voltage: float, 
                            rate_v_per_s: float = 0.1) -> None:
        """
        Ramps a *single* channel to a new target voltage at a specified rate.
        This is intended for intermediate adjustments while the system is
        running (i.e., not IDLE).
        
        To "stop" a single channel, set target_voltage to 0.0.
        To "start" a single channel, set target_voltage to its protocol voltage.

        Args:
            system_key (str): The key of the system to control (e.g., 'ti_A').
            channel_key (str): The key of the channel to ramp (e.g., 'A1').
            target_voltage (float): The new target voltage (V).
            rate_v_per_s (float): The ramp rate in Volts per second.
        """
        try:
            system = self.get_system(system_key)
            logger.info(f"Ramping channel '{channel_key}' in system '{system_key}' to {target_voltage}V at {rate_v_per_s} V/s.")
            system.ramp_channel_voltage(
                channel_key=channel_key,
                target_voltage=target_voltage,
                rate_v_per_s=rate_v_per_s
            )
        except KeyError:
            logger.error(f"Cannot ramp channel: System '{system_key}' not found.")
        except Exception as e:
            logger.error(f"An unexpected error occurred during single channel ramp: {e}", exc_info=True)

    def emergency_stop_all_systems(self) -> None:
        """
        Triggers an immediate, no-ramp emergency stop on all managed systems.
        Each TISystem is responsible for disabling its own hardware outputs.
        """
        logger.critical("--- EMERGENCY STOP TRIGGERED FOR ALL SYSTEMS ---")
        
        # Command all TISystem objects to E-Stop (sets voltage to 0)
        for system_key, system in self.ti_systems.items():
            try:
                system.emergency_stop()
            except Exception as e:
                logger.error(f"An error occurred during emergency stop for system '{system_key}': {e}", exc_info=True)
        
        # E-Stop should also immediately secure hardware, bypassing the
        # state monitor's debounce logic.
        self.disable_all_channels()
        self.abort()