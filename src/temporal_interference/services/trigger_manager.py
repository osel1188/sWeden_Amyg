# trigger_manager.py (MODIFIED)

import logging
import threading
import time
from typing import TYPE_CHECKING, Optional
from .system_monitor import SystemMonitor, TIManagerState
# MODIFIED: Import HardwareManager
from ..hardware.hardware_manager import HardwareManager

# Import only for static type checking
if TYPE_CHECKING:
    from .manager import TIManager # This is OK for type checking

logger = logging.getLogger(__name__)

class TriggerManager:
    """
    Monitors the overall TISystem state in a background thread and
    automatically manages hardware enable/disable/trigger states.

    - (IDLE -> RUNNING): Enables all channels, waits for a configurable delay,
      and then sends a software trigger ONLY if hardware is not already enabled.
    - (RUNNING -> IDLE): Waits for a 10-second debounce period. If
      still IDLE, disables all channels and sends an abort.
    """

    def __init__(self, 
                 monitor: SystemMonitor, 
                 hw_manager: Optional[HardwareManager], 
                 poll_interval_s: float = 0.1,
                 idle_debounce_s: float = 10.0,
                 trigger_delay_s: float = 1.0):
        """
        Initializes the TriggerManager.

        Args:
            monitor (SystemMonitor): The service used for polling system state.
            hw_manager (HardwareManager): The manager instance to call for actions.
            poll_interval_s (float): How often to check the state.
            idle_debounce_s (float): Time to wait in IDLE state before
                                     disabling hardware.
            trigger_delay_s (float): Time to wait between enabling channels
                                     and sending the software trigger.
        """
        self.monitor = monitor
        self.hw_manager = hw_manager
        self.poll_interval_s = poll_interval_s
        self.idle_debounce_s = idle_debounce_s
        self.trigger_delay_s = trigger_delay_s # MODIFIED: Store delay
        
        self._current_state = TIManagerState.IDLE
        self._idle_transition_time: Optional[float] = None
        self._hardware_enabled: bool = False 
        
        self._stop_event = threading.Event()
        self._monitor_thread: Optional[threading.Thread] = None
        
        if not self.hw_manager:
            logger.error("TriggerManager initialized without a HardwareManager. It will not be able to control hardware.")
        
        logger.info("TriggerManager initialized.")

    def start_monitoring(self) -> None:
        """
        Starts the background monitoring thread.
        """
        if not self.hw_manager:
            logger.warning("Cannot start TriggerManager: HardwareManager is missing.")
            return

        if self._monitor_thread and self._monitor_thread.is_alive():
            logger.warning("TriggerManager is already running.")
            return

        logger.info("Spawning background thread for hardware state monitoring.")
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._threaded_monitor_task,
            daemon=True
        )
        self._monitor_thread.start()

    def stop_monitoring(self) -> None:
        """
        Signals the background monitoring thread to stop.
        """
        logger.info("Stopping background hardware state monitoring...")
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
        logger.info("Hardware state monitoring stopped.")

    def _threaded_monitor_task(self) -> None:
        """
        [THREAD-TARGET] The main polling loop.
        """
        logger.info("[State Monitor Thread] Started.")
        
        # This check is redundant if start_monitoring checks, but provides
        # safety inside the thread loop.
        if not self.hw_manager:
            logger.error("[State Monitor Thread] Exiting: No HardwareManager provided.")
            return

        # Initialize state
        self._current_state = self.monitor.overall_state
        if self._current_state == TIManagerState.IDLE:
            self._idle_transition_time = time.time()
        else:
            self._idle_transition_time = None
        
        # Assume hardware is disabled on thread start
        self._hardware_enabled = False

        while not self._stop_event.is_set():
            try:
                # --- MODIFIED: Check for Hardware Connection FIRST ---
                # This check must be the first thing in the loop.
                if not self.hw_manager.is_connected:
                    logger.warning("[State Monitor Thread] HardwareManager is not connected (drivers not ready). Waiting...")
                    
                    # Force internal state to IDLE to ensure a safe state and
                    # proper re-triggering upon reconnection.
                    if self._current_state != TIManagerState.IDLE:
                        self._current_state = TIManagerState.IDLE
                        self._idle_transition_time = time.time() # Start debounce timer
                    
                    # MODIFICATION: If connection is lost, assume hardware is disabled.
                    self._hardware_enabled = False 
                    
                    # Wait for a longer interval before polling again
                    self._stop_event.wait(self.poll_interval_s * 10) # e.g., wait 1 second
                    continue # Skip main logic until connected

                # --- If connected, proceed with normal logic ---
                new_state = self.monitor.overall_state

                # --- Check for State Transitions ---

                # 1. Transition: IDLE -> RUNNING
                if new_state == TIManagerState.RUNNING and self._current_state == TIManagerState.IDLE:
                    logger.info("[State Monitor Thread] State change IDLE -> RUNNING.")
                    
                    # MODIFICATION: Only enable if hardware is currently disabled
                    if not self._hardware_enabled:
                        logger.info("Hardware is disabled. Enabling...")
                        self.hw_manager.enable_all_channels()
                        
                        # MODIFIED: Wait for the configured delay before triggering
                        logger.info(f"Waiting for {self.trigger_delay_s}s before sending trigger.")
                        self._stop_event.wait(self.trigger_delay_s) 
                        
                        if not self._stop_event.is_set():
                            logger.info("Sending software trigger.")
                            self.hw_manager.send_software_trigger()
                            self._hardware_enabled = True # Mark hardware as enabled
                        else:
                            # Handle case where stop was requested during the delay
                            logger.warning("Stop requested during trigger delay. Skipping trigger.")
                            # The hardware is enabled, but the main loop will handle the shutdown process
                    else:
                        logger.info("Hardware is already enabled (re-trigger within debounce). Skipping enable.")
                    
                    self._idle_transition_time = None # Cancel idle timer

                # 2. Transition: RUNNING -> IDLE
                elif new_state == TIManagerState.IDLE and self._current_state == TIManagerState.RUNNING:
                    logger.info(f"[State Monitor Thread] State change RUNNING -> IDLE. Starting {self.idle_debounce_s}s disable timer.")
                    self._idle_transition_time = time.time() # Start idle timer

                
                # --- Check for Persistent IDLE State ---
                if new_state == TIManagerState.IDLE and self._idle_transition_time is not None:
                    elapsed_idle_time = time.time() - self._idle_transition_time
                    
                    if elapsed_idle_time > self.idle_debounce_s:
                        
                        # MODIFICATION: Only disable if hardware is currently enabled
                        if self._hardware_enabled:
                            logger.info(f"[State Monitor Thread] System has been IDLE for {elapsed_idle_time:.1f}s. Securing hardware.")
                            self.hw_manager.disable_all_channels()
                            self.hw_manager.abort()
                            self._hardware_enabled = False # Mark hardware as disabled
                        else:
                            logger.info(f"[State Monitor Thread] System IDLE timeout, but hardware already secure.")
                        
                        self._idle_transition_time = None # Reset timer to prevent re-triggering
                
                # Update current state
                self._current_state = new_state

            except Exception as e:
                logger.error(f"[State Monitor Thread] An unexpected error occurred: {e}", exc_info=True)
                # Avoid busy-looping on error
            
            finally:
                # Wait for the next poll interval
                self._stop_event.wait(self.poll_interval_s)
        
        logger.info("[State Monitor Thread] Exiting.")