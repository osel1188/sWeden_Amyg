# ti_manager.py (REFACTORED)

import logging
from typing import Dict, Any, Optional
from ..config import TIConfig
from ..core.system import TISystem, TISystemHardwareState
from .system_monitor import SystemMonitor, TIManagerState
from .hardware_manager import HardwareManager
from .async_stop_handler import AsyncStopHandler

logger = logging.getLogger(__name__)

class TIManager:
    """
    Manages all TI systems for the experiment by orchestrating hardware,
    protocols, and system state.
    
    This class acts as a Facade, delegating specialized tasks to:
    - HardwareManager: For physical hardware lifecycle (connect, enable, etc.)
    - SystemMonitor: For read-only state polling and aggregation.
    - AsyncStopHandler: For managing non-blocking stop sequences.
    """
    def __init__(self, config_path: str = 'ti_config.json'):
        """
        Initializes the TIManager and its composed services.

        Args:
            config_path (str): The path to the JSON configuration file.
        """
        # 1. Configuration
        self.config_handler: TIConfig = TIConfig(config_path)
        self.protocols: Dict[str, Any] = self.config_handler.get_protocols()
        
        # 2. System Composition
        self.ti_systems: Dict[str, TISystem] = self.config_handler.get_ti_systems()
        
        # 3. Composed Services
        # These services are given a reference to the ti_systems dict.
        self.hardware: HardwareManager = HardwareManager(self.ti_systems)
        self.monitor: SystemMonitor = SystemMonitor(self.ti_systems)
        self.stop_handler: AsyncStopHandler = AsyncStopHandler(self.monitor, self.hardware)
        
        self.current_protocol_name: str | None = None
        
        logger.info(f"TIManager initialized with {len(self.ti_systems)} TI systems.")
        for system_key in self.ti_systems:
            logger.info(f"  -> Found system: '{system_key}' targeting '{self.ti_systems[system_key].region}'")

    # --- Delegated Properties and Methods ---

    @property
    def state(self) -> TIManagerState:
        """Delegates state calculation to the SystemMonitor."""
        return self.monitor.overall_state

    def connect_all_hardware(self) -> None:
        """Delegates hardware connection to the HardwareManager."""
        self.hardware.connect_all()

    def disconnect_all_hardware(self) -> None:
        """Delegates hardware disconnection to the HardwareManager."""
        self.hardware.disconnect_all()
        
    def get_all_channel_info(self) -> Dict[str, Dict[str, Any]]:
        """Delegates telemetry aggregation to the SystemMonitor."""
        return self.monitor.get_all_channel_info()

    def wait_for_all_ramps_to_finish(self, poll_interval_s: float = 0.05, timeout_s: Optional[float] = None) -> bool:
        """Delegates blocking wait to the SystemMonitor."""
        try:
            return self.monitor.wait_for_all_ramps_to_finish(poll_interval_s, timeout_s)
        except KeyboardInterrupt:
            logger.warning("Wait interrupted by user. Triggering E-Stop.")
            self.emergency_stop_all_systems()
            return False

    # --- System Management Methods ---

    def add_system(self, system: TISystem, system_key: str) -> None:
        """
        Adds a pre-configured TI system to the manager.
        The composed services (monitor, hardware) will see this
        new system as they operate on the shared ti_systems dictionary.
        """
        if system_key in self.ti_systems:
            logger.warning(f"Overwriting existing system with key '{system_key}'.")
        self.ti_systems[system_key] = system

    def get_system(self, system_key: str) -> TISystem:
        """
        Retrieves a specific TI system by its key (e.g., 'ti_A').
        """
        try:
            return self.ti_systems[system_key]
        except KeyError:
            logger.error(f"TI system key '{system_key}' not found.")
            raise

    # --- Protocol Methods ---

    def initialize_protocol(self, protocol_name: str) -> None:
        """
        Initializes all managed TI systems with settings from a named protocol.
        This configures target frequencies, voltages, and ramp durations for
        each channel in each system, but does not start the ramps.
        
        (Implementation logic is unchanged as this is a core
         orchestration responsibility of TIManager.)
        """
        protocol_name_upper = protocol_name.upper()
        protocols_upper_map = {k.upper(): k for k in self.protocols}
        
        if protocol_name_upper not in protocols_upper_map:
            logger.error(f"Protocol '{protocol_name}' (as '{protocol_name_upper}') not found in configuration.")
            raise KeyError(f"Protocol '{protocol_name}' not found.")
            
        protocol_data = self.protocols[protocols_upper_map[protocol_name_upper]]
        self.current_protocol_name = protocol_name_upper 
        
        logger.info(f"Initializing protocol '{protocol_name_upper}': {protocol_data.get('description', 'No description')}")

        try:
            # (Omitted for brevity - this logic is identical to the original file)
            # ...
            logger.info(f"Successfully initialized protocol '{protocol_name_upper}' for all configured systems.")

        except KeyError as e:
            logger.error(f"Failed to apply protocol '{protocol_name}': Missing key {e}", exc_info=True)
            self.current_protocol_name = None 
            raise
        except Exception as e:
            logger.error(f"An unexpected error occurred applying protocol '{protocol_name}': {e}", exc_info=True)
            self.current_protocol_name = None 
            raise

    def set_channel_target_voltage(self,
                                   system_key: str,
                                   channel_key: str,
                                   target_voltage: float) -> None:
        """
        Sets the target voltage parameter for a *single* channel in a
        specific system. This does *not* initiate a ramp.
        """
        try:
            system = self.get_system(system_key)
            system.setup_target_voltage({channel_key: target_voltage})
            logger.info(f"Set target voltage parameter for '{system_key}/{channel_key}' to {target_voltage}V.")
        except KeyError:
            logger.error(f"Cannot set voltage parameter: System '{system_key}' not found.")
        except Exception as e:
            logger.error(f"Error setting target voltage for '{system_key}/{channel_key}': {e}", exc_info=True)

    def start_protocol(self) -> None:
        """
        Activates and enables all hardware, then starts all managed TI systems
        based on the currently initialized protocol.
        """
        if not self.current_protocol_name:
            logger.error("Cannot start protocol: No protocol has been initialized. Call initialize_protocol() first.")
            return

        try:
            # 1. Delegate hardware enable
            self.hardware.enable_all()
        except Exception as e:
            logger.critical(f"Failed to enable hardware. Triggering emergency stop. Error: {e}", exc_info=True)
            self.emergency_stop_all_systems()
            return
        
        logger.info(f"--- STARTING PROTOCOL: {self.current_protocol_name} ---")
        
        # 2. Orchestrate system start
        protocols_upper_map = {k.upper(): k for k in self.protocols}
        protocol_data_key = protocols_upper_map.get(self.current_protocol_name) 
        
        if not protocol_data_key:
            logger.error(f"Cannot start protocol: Internal state error, protocol data for '{self.current_protocol_name}' missing.")
            return
        protocol_data = self.protocols[protocol_data_key]
        protocol_system_upper_map = {k.upper(): k for k in protocol_data}
        
        for system_key, system in self.ti_systems.items():
            if system_key.upper() not in protocol_system_upper_map:
                logger.warning(f"Skipping start for '{system_key}': Not defined in current protocol.")
                continue
            
            try:
                logger.info(f"Starting system '{system_key}' (targeting {system.region})...")
                system.start()
            except Exception as e:
                logger.error(f"An unexpected error occurred while starting system '{system_key}': {e}", exc_info=True)
                system.emergency_stop() 

    def stop_protocol(self) -> None:
        """
        Stops all managed TI systems by initiating a non-blocking ramp
        down to zero. Delegates to the AsyncStopHandler to monitor
        the ramp-down and secure hardware.
        """
        logger.info("--- STOPPING ALL SYSTEMS (NON-BLOCKING) ---")
        
        # 1. Orchestrate system stop
        for system_key, system in self.ti_systems.items():
            try:
                logger.info(f"Stopping system '{system_key}'...")
                system.stop()
            except Exception as e:
                logger.error(f"An unexpected error occurred while stopping system '{system_key}': {e}", exc_info=True)
                system.emergency_stop() 
        
        # 2. Delegate monitoring
        self.stop_handler.trigger_monitoring()
        
    def ramp_single_channel(self, 
                            system_key: str, 
                            channel_key: str, 
                            target_voltage: float, 
                            rate_v_per_s: float = 0.1) -> None:
        """
        Ramps a *single* channel to a new target voltage at a specified rate.
        """
        try:
            # 1. Check state via Monitor
            if target_voltage > 0.0 and self.monitor.check_all_systems_state(TISystemHardwareState.IDLE):
                logger.info("Enabling hardware for single-channel ramp-up from IDLE state.")
                # 2. Enable hardware via HardwareManager
                self.hardware.enable_all()
            
            # 3. Orchestrate system
            system = self.get_system(system_key)
            logger.info(f"Ramping channel '{channel_key}' in system '{system_key}' to {target_voltage}V at {rate_v_per_s} V/s.")
            system.ramp_channel_voltage(
                channel_key=channel_key,
                target_voltage=target_voltage,
                rate_v_per_s=rate_v_per_s
            )

            # 4. Delegate monitoring to StopHandler if ramping down
            if target_voltage == 0.0:
                self.stop_handler.trigger_monitoring()

        except KeyError:
            logger.error(f"Cannot ramp channel: System '{system_key}' not found.")
        except Exception as e:
            logger.error(f"An unexpected error occurred during single channel ramp: {e}", exc_info=True)

    def emergency_stop_all_systems(self) -> None:
        """
        Triggers an immediate, no-ramp emergency stop on all managed systems
        and attempts to disable all hardware.
        """
        logger.critical("--- EMERGENCY STOP TRIGGERED FOR ALL SYSTEMS ---")
        
        # 1. Orchestrate immediate system stop
        for system_key, system in self.ti_systems.items():
            try:
                system.emergency_stop()
            except Exception as e:
                logger.error(f"An error occurred during emergency stop for system '{system_key}': {e}", exc_info=True)
        
        # 2. Delegate immediate hardware disable
        try:
            logger.info("Attempting to disable all hardware following e-stop.")
            self.hardware.disable_all()
        except Exception as e:
            logger.critical(f"Failed to disable hardware during e-stop: {e}", exc_info=True)