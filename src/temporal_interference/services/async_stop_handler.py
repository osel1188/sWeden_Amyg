# async_stop_handler.py

import logging
import threading
from typing import Optional
from .system_monitor import SystemMonitor
from .hardware_manager import HardwareManager
from ..core.system import TISystemHardwareState

logger = logging.getLogger(__name__)

class AsyncStopHandler:
    """
    Manages a background thread to monitor non-blocking stop sequences.
    
    This class waits for all system ramps to finish and then disables
    hardware *only if* all systems have settled into an IDLE state.
    """
    
    def __init__(self, monitor: SystemMonitor, hardware: HardwareManager):
        """
        Initializes the AsyncStopHandler.

        Args:
            monitor (SystemMonitor): The service used for polling system state.
            hardware (HardwareManager): The service used to disable hardware.
        """
        self.monitor = monitor
        self.hardware = hardware
        self._stop_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def trigger_monitoring(self) -> None:
        """
        Triggers the background monitoring thread.
        
        If the thread is already running, this request is ignored.
        """
        with self._lock:
            if self._stop_thread and self._stop_thread.is_alive():
                logger.warning(
                    "Stop procedure monitoring is already in progress. "
                    "The existing thread will monitor any new ramp-downs."
                )
                return

            logger.info("Spawning background thread for hardware ramp-down monitoring and deactivation.")
            self._stop_thread = threading.Thread(
                target=self._threaded_stop_task,
                daemon=True
            )
            self._stop_thread.start()

    def _threaded_stop_task(self) -> None:
        """
        [THREAD-TARGET] Blocks until all ramps are finished, then
        secures all hardware if appropriate.
        """
        try:
            # 1. Wait for all ramp-down activity to cease
            all_finished = self.monitor.wait_for_all_ramps_to_finish(timeout_s=30.0) # 30s timeout
            
            if not all_finished:
                logger.warning(
                    "[Stop Thread] Wait for ramps timed out or was interrupted. "
                    "Hardware will remain enabled. Manual E-Stop may be required."
                )
                return

            # 2. Check the final state
            all_idle = self.monitor.check_all_systems_state(TISystemHardwareState.IDLE)
            
            if all_idle:
                logger.info("[Stop Thread] All systems are IDLE. Securing hardware...")
                self.hardware.disable_all()
            else:
                logger.warning(
                    "[Stop Thread] All ramps finished, but not all systems are IDLE. "
                    "A new ramp-up was likely initiated. Hardware will remain enabled."
                )
        
        except Exception as e:
            logger.error(f"[Stop Thread] An unexpected error occurred: {e}", exc_info=True)
            # We do not trigger an e-stop from a background thread,
            # but we log the failure to disable hardware.
        
        finally:
            logger.info("[Stop Thread] Stop monitoring procedure finished.")
            with self._lock:
                self._stop_thread = None