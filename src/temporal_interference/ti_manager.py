# ti_manager.py 

from typing import List, Dict, Any, Optional
import logging
import time
import threading # <-- ADDED
from .ti_config import TIConfig
from .ti_system import TISystem, TISystemState
from .waveform_generators.waveform_generator import AbstractWaveformGenerator

# --- Define the module-level logger ---
logger = logging.getLogger(__name__)

class TIManager:
    """
    Manages all TI systems for the experiment by loading and interpreting
    a configuration file. Each TI system corresponds to a target region
    and contains one or more TIChannels.
    
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
        
        # The TIManager requests the system list from the config handler,
        # which acts as a factory.
        self.ti_systems: Dict[str, TISystem] = self.config_handler.get_ti_systems()
        self.protocols: Dict[str, Any] = self.config_handler.get_protocols()
        
        self.current_protocol_name: str | None = None
        self._stop_thread: Optional[threading.Thread] = None # <-- ADDED
        
        logger.info(f"TIManager initialized with {len(self.ti_systems)} TI systems from config.")
        for system_key in self.ti_systems:
            logger.info(f"  -> Found system: '{system_key}' targeting '{self.ti_systems[system_key].region}'")

    # --- Hardware Connection/Disconnection Methods ---

    def _get_all_hardware_generators(self) -> set[AbstractWaveformGenerator]:
        """
        Collects a set of all unique waveform generator hardware instances
        managed by this manager's systems.
        """
        all_generators: set[AbstractWaveformGenerator] = set()
        for system in self.ti_systems.values():
            for channel in system.channels.values():
                all_generators.add(channel.generator)
        return all_generators

    def connect_all_hardware(self) -> None:
        """
        Connects to all unique hardware resources (waveform generators)
        managed by this manager.
        """
        logger.info("Connecting to all hardware resources...")
        hardware = self._get_all_hardware_generators()
        
        if not hardware:
            logger.warning("No hardware generators found to connect.")
            return

        for i, generator in enumerate(hardware):
            try:
                logger.info(f"Connecting to hardware '{generator.resource_id}' ({i+1}/{len(hardware)})...")
                generator.connect()
                logger.info(f"Successfully connected to '{generator.resource_id}'.")
            except Exception as e:
                logger.error(f"Failed to connect to hardware '{generator.resource_id}': {e}", exc_info=True)
                # Continue attempting to connect to other devices
        
        logger.info(f"Hardware connection attempt finished for {len(hardware)} devices.")

    def disconnect_all_hardware(self) -> None:
        """
        Disconnects from all unique hardware resources (waveform generators)
        managed by this manager.
        """
        logger.info("Disconnecting from all hardware resources...")
        hardware = self._get_all_hardware_generators()

        if not hardware:
            logger.warning("No hardware generators found to disconnect.")
            return

        for i, generator in enumerate(hardware):
            try:
                logger.info(f"Disconnecting from hardware '{generator.resource_id}' ({i+1}/{len(hardware)})...")
                generator.disconnect()
                logger.info(f"Successfully disconnected from '{generator.resource_id}'.")
            except Exception as e:
                logger.error(f"Failed to disconnect from hardware '{generator.resource_id}': {e}", exc_info=True)
        
        logger.info(f"Hardware disconnection finished for {len(hardware)} devices.")

    # --- End of new methods ---

    def add_system(self, system: TISystem, system_key: str) -> None:
        """Adds a pre-configured TI system to the manager."""
        if system_key in self.ti_systems:
            logger.warning(f"Overwriting existing system with key '{system_key}'.")
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
            logger.error(f"TI system key '{system_key}' not found.")
            raise

    # --- Replaces set_protocol ---
    def initialize_protocol(self, protocol_name: str) -> None:
        """
        Initializes all managed TI systems with settings from a named protocol.
        This configures target frequencies, voltages, and ramp durations for
        each channel in each system, but does not start the ramps.
        
        This method is case-insensitive for protocol names, system keys,
        and channel keys.
        
        Args:
            protocol_name (str): The name of the protocol (e.g., "STIM", "SHAM").
            
        Raises:
            KeyError: If the protocol_name or a required setting is not found.
        """
        # --- Make protocol name lookup case-insensitive ---
        protocol_name_upper = protocol_name.upper()
        # Create a {UPPER_KEY: original_key} map for lookup
        protocols_upper_map = {k.upper(): k for k in self.protocols}
        
        if protocol_name_upper not in protocols_upper_map:
            logger.error(f"Protocol '{protocol_name}' (as '{protocol_name_upper}') not found in configuration.")
            raise KeyError(f"Protocol '{protocol_name}' not found.")
            
        # Get protocol data using the *original* case-preserved key
        protocol_data = self.protocols[protocols_upper_map[protocol_name_upper]]
        self.current_protocol_name = protocol_name_upper # Store the canonical (upper) name
        
        logger.info(f"Initializing protocol '{protocol_name_upper}': {protocol_data.get('description', 'No description')}")

        try:
            # --- Create uppercase map for system keys in protocol ---
            protocol_system_upper_map = {k.upper(): k for k in protocol_data}

            # Iterate over each system managed by this manager (e.g., "ti_A", "ti_B")
            for system_key, system in self.ti_systems.items():
                
                # --- Make system key lookup case-insensitive ---
                system_key_upper = system_key.upper()
                if system_key_upper not in protocol_system_upper_map:
                
                    logger.warning(f"Protocol '{protocol_name_upper}' has no settings for system '{system_key}' (as '{system_key_upper}'). Skipping.")
                    continue
                
                # --- Get settings using original case-preserved key ---
                protocol_settings = protocol_data[protocol_system_upper_map[system_key_upper]]
                
                channel_settings_list = protocol_settings.get('channel_settings', [])
                
                if not channel_settings_list:
                    logger.error(f"Protocol error: System '{system_key}' has no 'channel_settings' defined.")
                    continue

                # Build dictionaries for the TISystem's N-channel API
                target_voltages: Dict[str, float] = {}
                target_frequencies: Dict[str, float] = {}
                ramp_durations: Dict[str, float] = {}

                # --- Create uppercase map for hardware channels ---
                system_channel_upper_map = {k.upper(): k for k in system.channels}
                

                for settings in channel_settings_list:
                    # --- Make channel key lookup case-insensitive ---
                    channel_key_from_protocol = settings['channel']
                    channel_key_upper = channel_key_from_protocol.upper()
                    
                    # Validate that the channel from the protocol exists in the system (case-insensitive)
                    if channel_key_upper not in system_channel_upper_map:
                        logger.error(f"Protocol mismatch: Channel '{channel_key_from_protocol}' (as '{channel_key_upper}') (for system '{system_key}') not found in hardware config. Skipping channel.")
                        continue
                    
                    # Get the *original* hardware channel key (e.g., 'A1' or 'a1')
                    original_hardware_channel_key = system_channel_upper_map[channel_key_upper]
                    
                    # Assign settings using the original, case-preserved hardware key
                    target_voltages[original_hardware_channel_key] = settings['target_voltage_V']
                    target_frequencies[original_hardware_channel_key] = settings['frequency_hz']
                    ramp_durations[original_hardware_channel_key] = settings['ramp_duration_s']
                    
                
                # Apply settings to the TISystem object using the new API
                system.setup_target_voltage(target_voltages)
                system.setup_frequencies(target_frequencies)
                system.setup_ramp_durations(ramp_durations)
                system.apply_config()
                
            logger.info(f"Successfully initialized protocol '{protocol_name_upper}' for all configured systems.")

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
            # We call it with a single-item dict.
            system.setup_target_voltage({channel_key: target_voltage})
            logger.info(f"Set target voltage parameter for '{system_key}/{channel_key}' to {target_voltage}V.")
        except KeyError:
            logger.error(f"Cannot set voltage parameter: System '{system_key}' not found.")
        except Exception as e:
            logger.error(f"Error setting target voltage for '{system_key}/{channel_key}': {e}", exc_info=True)

    # --- Replaces run_all_systems ---
    def _enable_systems(self) -> None:
        # --- Prepare hardware before starting systems ---
        try:
            hardware = self._get_all_hardware_generators()
            logger.info(f"Preparing {len(hardware)} hardware generator(s)...")
            
            for gen in hardware:
                logger.debug(f"Activating channels on {gen.resource_id}")
                gen.activate_channels()
                
            for gen in hardware:
                logger.debug(f"Enabling device {gen.resource_id}")
                gen.enable_generation()
            
            logger.info("Hardware preparation complete.")
        except Exception as e:
            logger.critical(f"Failed to prepare hardware for protocol start: {e}", exc_info=True)
            self.emergency_stop_all_systems()
            return

    def _disable_systems(self) -> None:
        # --- Prepare hardware before starting systems ---
        try:
            hardware = self._get_all_hardware_generators()
            logger.info(f"Disabling {len(hardware)} hardware generator(s)...")
            
            for gen in hardware:
                logger.debug(f"Disabling device {gen.resource_id}")
                gen.disable_generation()

            for gen in hardware:
                logger.debug(f"Deactivating channels on {gen.resource_id}")
                gen.deactivate_channels()
                
            logger.info("Hardware disabling complete.")
        except Exception as e:
            logger.critical(f"Failed to disable hardware for protocol start: {e}", exc_info=True)
            self.emergency_stop_all_systems()
            return

    def start_protocol(self) -> None:
        """
        Activates and enables all hardware, then starts all managed TI systems
        based on the currently initialized protocol.
        
        This will initiate the non-blocking voltage ramp-up to the target voltages
        for all systems defined in the protocol.
        """
        if not self.current_protocol_name:
            logger.error("Cannot start protocol: No protocol has been initialized. Call initialize_protocol() first.")
            return

        self._enable_systems()
        logger.info(f"--- STARTING PROTOCOL: {self.current_protocol_name} ---")
        
        # --- Case-insensitive check for protocol data ---
        # (Using the same logic as initialize_protocol)
        protocols_upper_map = {k.upper(): k for k in self.protocols}
        protocol_data_key = protocols_upper_map.get(self.current_protocol_name) # current_protocol_name is already upper
        
        if not protocol_data_key:
             # This should be impossible if initialize_protocol succeeded, but good practice
            logger.error(f"Cannot start protocol: Internal state error, protocol data for '{self.current_protocol_name}' missing.")
            return
        protocol_data = self.protocols[protocol_data_key]
        protocol_system_upper_map = {k.upper(): k for k in protocol_data}
        

        for system_key, system in self.ti_systems.items():
            # --- Case-insensitive check ---
            if system_key.upper() not in protocol_system_upper_map:
            
                logger.warning(f"Skipping start for '{system_key}': Not defined in current protocol.")
                continue
            
            try:
                logger.info(f"Starting system '{system_key}' (targeting {system.region})...")
                # TISystem.start() is now parameter-less and non-blocking
                system.start()
                
            except Exception as e:
                logger.error(f"An unexpected error occurred while starting system '{system_key}': {e}", exc_info=True)
                system.emergency_stop() # Ensure safety

    # --- Replaces stop_all_systems ---
    def stop_protocol(self) -> None:
        """
        Stops all managed TI systems by initiating a non-blocking ramp
        down to zero. A background thread is spawned to wait for the
        ramps to complete, after which it disables and deactivates all hardware.
        """
        # --- Run hardware deactivation in a thread ---
        if self._stop_thread and self._stop_thread.is_alive():
            logger.warning("Stop procedure is already in progress. Ignoring request.")
            return

        logger.info("--- STOPPING ALL SYSTEMS (NON-BLOCKING) ---")
        for system_key, system in self.ti_systems.items():
            try:
                logger.info(f"Stopping system '{system_key}'...")
                # TISystem.stop() is now parameter-less and non-blocking
                system.stop()
            except Exception as e:
                logger.error(f"An unexpected error occurred while stopping system '{system_key}': {e}", exc_info=True)
                system.emergency_stop() # Ensure safety
        
        logger.info("Spawning background thread for hardware ramp-down monitoring and deactivation.")
        self._stop_thread = threading.Thread(
            target=self._threaded_stop_task,
            daemon=True
        )
        self._stop_thread.start()
        
        
    def _threaded_stop_task(self) -> None:
        """
        [THREAD-TARGET] Blocks until all ramps are finished, then
        secures all hardware.
        """
        try:
            logger.info("[Stop Thread] Waiting for all system ramps to complete...")
            all_finished = self.wait_for_all_ramps_to_finish()
            
            if not all_finished:
                logger.warning("[Stop Thread] Wait for ramps timed out or was interrupted. Triggering emergency stop.")
                self.emergency_stop_all_systems()
                return

            all_idle = self.check_all_systems_state(TISystemState.IDLE)
            
            if all_idle:
                logger.info("[Stop Thread] All systems are IDLE. Securing hardware...")
                self._disable_systems()
            else:
                logger.error("[Stop Thread] All ramps finished, but not all systems are IDLE. Hardware state may be unknown. Triggering emergency stop.")
                self.emergency_stop_all_systems()
        
        except Exception as e:
            logger.error(f"[Stop Thread] An unexpected error occurred: {e}", exc_info=True)
            self.emergency_stop_all_systems()

        finally:
            logger.info("[Stop Thread] Stop procedure finished.")
            self._stop_thread = None # Allow next stop
    
    def check_all_systems_state(self, target_state: TISystemState) -> bool:
        """
        Checks if all managed TI systems are in the specified state.

        Args:
            target_state (TISystemState): The state to check for.

        Returns:
            bool: True if all systems are in the target state, False otherwise.
        """
        if not self.ti_systems:
            return True  # Vacuously true if no systems are managed
        
        return all(system.state == target_state for system in self.ti_systems.values())

    def wait_for_all_ramps_to_finish(self, poll_interval_s: float = 0.05, timeout_s: Optional[float] = None) -> bool:
        """
        Blocks the calling thread until all managed TISystem instances
        are no longer ramping.

        Args:
            poll_interval_s (float): The time to wait between checks.
            timeout_s (float | None): Maximum time to wait. If None,
                                      waits indefinitely.

        Returns:
            bool: True if all ramps finished, False if the wait timed out.
        """
        start_time = time.time()

        try:
            while any(system.is_ramping for system in self.ti_systems.values()):
                if timeout_s is not None:
                    elapsed = time.time() - start_time
                    if elapsed > timeout_s:
                        logger.warning(f"Wait for ramps timed out after {elapsed:.2f}s.")
                        return False
                
                time.sleep(poll_interval_s)
        
        except KeyboardInterrupt:
            logger.warning("Wait for ramps interrupted by user (KeyboardInterrupt).")
            self.emergency_stop_all_systems()
            return False

        logger.info("All system ramps have completed.")
        return True

    def ramp_single_channel(self, 
                            system_key: str, 
                            channel_key: str, 
                            target_voltage: float, 
                            rate_v_per_s: float = 0.1) -> None:
        """
        Ramps a *single* channel to a new target voltage at a specified rate.
        This is intended for intermediate adjustments while the system is
        running (i.e., not IDLE).
        
        If this call initiates a ramp-up from a fully IDLE state, it will
        synchronously enable hardware before returning.
        
        If this call initiates a ramp-down to 0.0 V, it will return
        immediately and spawn a background thread to monitor the ramp.
        The thread will disable hardware *only if* all systems become
        IDLE after the ramp completes.

        Args:
            system_key (str): The key of the system to control (e.g., 'ti_A').
            channel_key (str): The key of the channel to ramp (e.g., 'A1').
            target_voltage (float): The new target voltage (V).
            rate_v_per_s (float): The ramp rate in Volts per second.
        """
        try:
            # --- Handle Ramp-Up from IDLE state ---
            # This must be synchronous to ensure hardware is ready
            if target_voltage > 0.0 and self.check_all_systems_state(TISystemState.IDLE):
                logger.info("Enabling hardware for single-channel ramp-up from IDLE state.")
                self._enable_systems()
            
            # --- Get system and initiate ramp ---
            system = self.get_system(system_key)
            
            logger.info(f"Ramping channel '{channel_key}' in system '{system_key}' to {target_voltage}V at {rate_v_per_s} V/s.")
            system.ramp_channel_voltage(
                channel_key=channel_key,
                target_voltage=target_voltage,
                rate_v_per_s=rate_v_per_s
            )

            # --- Handle Ramp-Down (Asynchronous) ---
            # If ramping down to zero, spawn a thread to monitor
            # and disable hardware if all systems become IDLE.
            if target_voltage == 0.0:
                if self._stop_thread and self._stop_thread.is_alive():
                    logger.warning(
                        "A stop procedure is already running. The new ramp-down "
                        "will be monitored by the existing thread."
                    )
                    return # The existing thread will handle it

                logger.info("Spawning background thread for single-channel ramp-down monitoring and hardware deactivation.")
                self._stop_thread = threading.Thread(
                    target=self._threaded_stop_task,
                    daemon=True
                )
                self._stop_thread.start()

        except KeyError:
            logger.error(f"Cannot ramp channel: System '{system_key}' not found.")
        except Exception as e:
            logger.error(f"An unexpected error occurred during single channel ramp: {e}", exc_info=True)

    def emergency_stop_all_systems(self) -> None:
        """
        Triggers an immediate, no-ramp emergency stop on all managed systems.
        """
        logger.critical("--- EMERGENCY STOP TRIGGERED FOR ALL SYSTEMS ---")
        for system_key, system in self.ti_systems.items():
            try:
                system.emergency_stop()
            except Exception as e:
                logger.error(f"An error occurred during emergency stop for system '{system_key}': {e}", exc_info=True)
                
    def get_all_channel_info(self) -> Dict[str, Dict[str, Any]]:
        """
        Retrieves detailed state information for all channels in all systems.

        Returns:
            Dict[str, Dict[str, Any]]: A nested dictionary:
            {
                "system_key": {
                    "channel_key": { ...info... }
                }
            }
        """
        all_info: Dict[str, Dict[str, Any]] = {}
        for system_key, system in self.ti_systems.items():
            system_info: Dict[str, Any] = {}
            for channel_key, channel in system.channels.items():
                channel_info = {
                    "region": system.region,
                    "system_state": system.state.name,
                    "is_system_ramping": system.is_ramping,
                    "target_voltage": channel.target_voltage,
                    "target_frequency": channel.target_frequency,
                    "ramp_duration_s": channel.ramp_duration_s,
                    "current_voltage": channel.get_current_voltage(),
                    "electrode_pair": str(channel.pair),
                    "wavegen_id": channel.generator.resource_id,
                    "wavegen_channel": channel.wavegen_channel
                }
                system_info[channel_key] = channel_info
            all_info[system_key] = system_info
        return all_info