# system_monitor.py (MODIFIED)

import logging
import time
from enum import Enum, auto
from typing import Dict, Any, Optional
from ..core.system import TISystem, TISystemHardwareState

logger = logging.getLogger(__name__)

# --- TIManagerState Enum ---
class TIManagerState(Enum):
    """Defines the discrete operational states of the TISystem."""
    IDLE = auto()
    RUNNING = auto()

class SystemMonitor:
    """
    Handles all read-only state aggregation and polling for a collection
    of TISystem objects. It does not modify any system state.
    """
    def __init__(self, ti_systems: Dict[str, TISystem]):
        """
        Initializes the SystemMonitor.

        Args:
            ti_systems (Dict[str, TISystem]): A reference to the dictionary
                of TI systems managed by the TIManager.
        """
        self.ti_systems = ti_systems

    @property
    def overall_state(self) -> TIManagerState:
        """
        Dynamically derives the TIManager's state by polling all subsystems.
        
        - If *any* system is not IDLE, the manager is considered RUNNING.
        - If *all* systems are IDLE, the manager is considered IDLE.
        """
        if not self.ti_systems:
            return TIManagerState.IDLE
            
        for system in self.ti_systems.values():
            if system.hardware_state != TISystemHardwareState.IDLE:
                return TIManagerState.RUNNING
        
        return TIManagerState.IDLE

    def check_all_systems_state(self, target_state: TISystemHardwareState) -> bool:
        """
        Checks if all managed TI systems are in the specified state.

        Args:
            target_state (TISystemHardwareState): The state to check for.

        Returns:
            bool: True if all systems are in the target state, False otherwise.
        """
        if not self.ti_systems:
            return True 
        
        return all(system.hardware_state == target_state for system in self.ti_systems.values())

    def wait_for_all_ramps_to_finish(self, 
                                     poll_interval_s: float = 0.05, 
                                     timeout_s: Optional[float] = None) -> bool:
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
        logger.info("Waiting for all system ramps to complete...")

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
            # Note: E-stop is handled by TIManager, not the monitor.
            return False

        logger.info("All system ramps have completed.")
        return True

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
                    "system_state": system.hardware_state.name,
                    "is_system_ramping": system.is_ramping,
                    "target_voltage": channel.target_voltage,
                    "target_frequency": channel.target_frequency,
                    "ramp_duration_s": channel.ramp_duration_s,
                    "current_voltage": channel.get_current_voltage(), # Cached state
                    "electrode_pair": str(channel.pair),
                    "driver_id": channel.driver_id, # MODIFIED
                    "physical_channel": channel.wavegen_channel # MODIFIED
                }
                system_info[channel_key] = channel_info
            all_info[system_key] = system_info
        return all_info