# ti_system.py (MODIFIED)

import logging
import sys
import time
import threading
import concurrent.futures
from enum import Enum, auto
from typing import List, Callable, Tuple, Optional, Dict
import numpy as np

# Local imports (assumed)
from .channel import TIChannel
from ..hardware.hardware_manager import HardwareManager
from ..hardware.waveform_generator import (
    OutputState
)

# --- Define the module-level logger ---
logger = logging.getLogger(__name__)

# --- TISystemLogicState Enum (MODIFIED) ---
class TISystemLogicState(Enum):
    """Defines the discrete operational *logic* states of the TISystem."""
    IDLE = auto()
    WAITING_FOR_TRIGGER = auto()
    RAMPING_UP = auto()
    RUNNING_AT_TARGET = auto()
    RAMPING_DOWN = auto()
    RAMPING_INTERMEDIATE = auto()
    RUNNING_INTERMEDIATE = auto()
    ERROR = auto()

# --- TISystemHardwareState Enum (Unchanged) ---
class TISystemHardwareState(Enum):
    """Defines the *physical* hardware state based on live queries."""
    IDLE = auto()
    RUNNING = auto()
    ERROR = auto()


class TISystem:
    def __init__(self,
                 region: str,
                 channels: Dict[str, TIChannel],
                 status_update_func: Callable[[str, str], None] = None,
                 progress_callback: Optional[Callable[[str, float], None]] = None):

        if not channels:
            raise ValueError("TISystem must be initialized with at least one channel.")
            
        self.region: str = region
        
        # --- Callbacks for Decoupling (Unchanged) ---
        self._status_update_func: Callable[[str, str], None] = status_update_func or self._default_status_update
        self._progress_callback: Optional[Callable[[str, float], None]] = progress_callback or self._default_progress_update
        self._spinner = ['◜', '◝', '◞', '◟']

        # --- State Management (Unchanged) ---
        self._logic_state: TISystemLogicState = TISystemLogicState.IDLE
        self._state_lock = threading.RLock()
        self._ramp_thread: Optional[threading.Thread] = None
        self._trigger_event = threading.Event() 

        # --- Encapsulated Channels (Unchanged) ---
        self.channels: Dict[str, TIChannel] = channels
        
        # --- Operational Parameters (Unchanged) ---
        self.ramp_time_step_s: float = 0.1 # 10 Hz: The current waveform gen cannot receive messages faster.

    # --- _default_status_update (Unchanged) ---
    def _default_status_update(self, message: str, level: str):
        """Default status handler if none is provided."""
        log_level = getattr(logging, level.upper(), logging.INFO)
        logger.log(log_level, f"TISystem ({self.region}): {message}")

    # --- _default_progress_update (Unchanged) ---
    def _default_progress_update(self, region_name: str, progress: float):
        """Default progress handler (console spinner) if none is provided."""
        if progress < 100.0:
            spinner_char = self._spinner[int(time.time() * 10) % 4]
            sys.stdout.write(f'\r\033[K Ramping {region_name} ... {spinner_char} {progress:.1f}%')
        else:
            sys.stdout.write(f'\r\033[K Ramping {region_name} ... Done. 100.0% \n')
        sys.stdout.flush()

    # --- logic_state (Unchanged) ---
    @property
    def logic_state(self) -> TISystemLogicState:
        """Returns the current *intended* operational state of the system."""
        with self._state_lock:
            return self._logic_state

    # --- Hardware State Property (Unchanged) ---
    @property
    def hardware_state(self) -> TISystemHardwareState:
        """
        Queries the *cached* hardware state by checking channel voltages.
        Returns RUNNING if any channel voltage is non-zero, IDLE otherwise.
        This operation is fast and does NOT perform live I/O, preventing
        lock contention with active ramps.
        """
        try:
            for channel in self.channels.values():
                if 0.03 < abs(channel.get_current_voltage()):
                    return TISystemHardwareState.RUNNING
                    
            return TISystemHardwareState.IDLE
            
        except Exception as e:
            logger.error(f"Failed to query cached hardware state for {self.region}: {e}", exc_info=True)
            self._status_update_func(f"Failed to get cached hardware state: {e}", "error")
            return TISystemHardwareState.ERROR

    # --- is_running (Unchanged) ---
    @property
    def is_running(self) -> bool:
        """
        True if system is *logically* at target or intermediate voltage.
        """
        with self._state_lock:
            return self._logic_state in {
                TISystemLogicState.RUNNING_AT_TARGET, 
                TISystemLogicState.RUNNING_INTERMEDIATE
            }

    # --- is_ramping (Unchanged) ---
    @property
    def is_ramping(self) -> bool:
        """True if a ramp (up, down, or intermediate) is in progress."""
        with self._state_lock:
            return self._ramp_thread is not None and self._ramp_thread.is_alive()

    # --- emergency_stop_triggered (Unchanged) ---
    @property
    def emergency_stop_triggered(self) -> bool:
        """True if the stop event has been set. Thread-safe."""
        return self._trigger_event.is_set()

    # --- Hardware Lifecycle Methods (Unchanged) ---

    def connect_all(self):
        """
        Connects to all hardware resources via the HardwareManager.
        Called by TIManager.
        """
        self._status_update_func(f"Connecting hardware for system {self.region}...", "info")
        _hw_manager: HardwareManager = next(iter(self.channels.values())).hw_manager
        _hw_manager.connect_all()

    def disconnect_all(self):
        """
        Disconnects from all hardware resources via the HardwareManager.
        Called by TIManager.
        """
        self._status_update_func(f"Disconnecting hardware for system {self.region}...", "info")
        _hw_manager: HardwareManager = next(iter(self.channels.values())).hw_manager
        _hw_manager.disconnect_all()
    
    # --- setup_* methods (Unchanged) ---
    
    def _validate_channel_keys(self, data: Dict[str, float], operation: str) -> bool:
        """Helper to validate keys in setup methods."""
        for key in data:
            if key not in self.channels:
                self._status_update_func(f"Invalid channel key '{key}' for {operation}.", "error")
                logger.error(f"Invalid channel key '{key}' for {operation}. Available: {list(self.channels.keys())}")
                return False
        return True

    def setup_target_voltage(self, voltages: Dict[str, float]) -> None:
        """Sets the target voltage for one or more specified channels."""
        if not self._validate_channel_keys(voltages, "setup_target_voltage"):
            return
            
        log_msgs = []
        for key, volt in voltages.items():
            self.channels[key].setup_target_voltage(volt)
            log_msgs.append(f"{key}={volt} V")
        logger.info(f"Region {self.region} target voltages set to: {', '.join(log_msgs)}.")

    def set_frequencies(self, frequencies: Dict[str, float]) -> None:
        """Sets the frequency for one or more specified channels."""
        if not self._validate_channel_keys(frequencies, "setup_frequencies"):
            return
        
        log_msgs = []
        for key, freq in frequencies.items():
            self.channels[key].set_frequency(freq)
            log_msgs.append(f"{key}={freq} Hz")
        logger.info(f"Region {self.region} frequencies set to: {', '.join(log_msgs)}.")

    def set_ramp_durations(self, durations: Dict[str, float]) -> None:
        """Sets the ramp duration for one or more specified channels."""
        if not self._validate_channel_keys(durations, "setup_ramp_durations"):
            return
        
        log_msgs = []
        for key, dur in durations.items():
            self.channels[key].set_ramp_duration(dur)
            log_msgs.append(f"{key}={dur}s")
        logger.info(f"Region {self.region} ramp durations set to: {', '.join(log_msgs)}.")

    def set_ramp_duration(self, duration_s: float) -> None:
        """Sets the same ramp duration for *all* channels."""
        logger.warning("setup_ramp_duration(s) is deprecated. Use setup_ramp_durations(dict) for per-channel control.")
        all_channel_durations = {key: duration_s for key in self.channels}
        self.set_ramp_durations(all_channel_durations)

    # --- start method (Unchanged) ---
    def start(self) -> None:
        """
        Applies frequencies, turns on outputs, and starts a non-blocking
        ramp up to target voltage for all channels.
        """
        with self._state_lock:
            if self.is_ramping:
                self._status_update_func(f"System {self.region} is already ramping.", "warning")
                return
            
            if self._logic_state != TISystemLogicState.IDLE:
                self._status_update_func(f"System {self.region} is not IDLE (state: {self._logic_state.name}). Cannot start.", "warning")
                return

            self._status_update_func(f"Starting system {self.region}...", "info")
            
            self._trigger_event.clear()

            self._logic_state = TISystemLogicState.WAITING_FOR_TRIGGER 
            
            self._ramp_thread = threading.Thread(
                target=self._threaded_start_task, 
                daemon=True
            )
            self._ramp_thread.start()
    
    # --- _threaded_start_task (Unchanged) ---
    def _threaded_start_task(self) -> None:
        """[THREAD-TARGET] Contains the blocking logic for setup and ramp-up."""
        try:
            # --- MODIFICATION: Wait for hardware enabling and trigger ---
            if not self._trigger_event.is_set():
                _hw_manager: HardwareManager = next(iter(self.channels.values())).hw_manager
                trigger_event = _hw_manager.trigger_event
                
                # State is already WAITING_FOR_TRIGGER (set by start())
                self._status_update_func(f"System {self.region} outputs enabled. Waiting for hardware trigger...", "info")
                logger.info(f"System {self.region} waiting for hardware trigger event...")
                
                # This call blocks until the event is set by HardwareManager.send_software_trigger()
                trigger_event.wait()
                
                if self._trigger_event.is_set():
                     logger.warning(f"System {self.region} stop event triggered while waiting for trigger.")
                     raise Exception("Stop event triggered during trigger wait")
                
                # --- MODIFIED: Transition state from WAITING to RAMPING_UP ---
                with self._state_lock:
                    # Check again in case stop was called right after wait() but before lock
                    if self._trigger_event.is_set():
                         raise Exception("Stop event triggered immediately after trigger wait")
                    self._logic_state = TISystemLogicState.RAMPING_UP
                # --- END MODIFICATION ---
                
                logger.info(f"System {self.region} hardware trigger event received. Starting ramp.")
                self._status_update_func(f"System {self.region} trigger received. Ramping up...", "info")
            # --- END MODIFICATION ---

            # 2. Ramp up to target voltages
            target_voltages_for_ramp = {
                key: ch.target_voltage for key, ch in self.channels.items()
            }
            ramp_durations = {
                key: ch.ramp_duration_s for key, ch in self.channels.items()
            }
            self.ramp(target_voltages_for_ramp, ramp_durations)
            
            # 3. Update state on success
            with self._state_lock:
                if not self._trigger_event.is_set():
                    self._logic_state = TISystemLogicState.RUNNING_AT_TARGET
                    self._status_update_func(f"System {self.region} is running at target.", "success")
                else:
                    self._logic_state = TISystemLogicState.IDLE
                    
        except Exception as e:
            if not self._trigger_event.is_set():
                # Only log as error if it wasn't a deliberate stop
                error_msg = f"Failed to start TISystem {self.region}: {e}"
                logger.error(error_msg, exc_info=True)
                self._status_update_func(f"Error starting {self.region}: {e}", "error")
                with self._state_lock:
                    self._logic_state = TISystemLogicState.ERROR
            else:
                logger.warning(f"TISystem {self.region} start task was interrupted by stop event.")
                with self._state_lock:
                    self._logic_state = TISystemLogicState.IDLE
            
            self.emergency_stop() # Ensure hardware is safe regardless
        finally:
            with self._state_lock:
                self._ramp_thread = None

    # --- stop methods (Unchanged) ---
    def stop(self) -> None:
        """
        Starts a non-blocking ramp down to zero for all channels 
        and turns off outputs. Uses the internally configured ramp durations.
        """
        with self._state_lock:
            if self.is_ramping:
                self._status_update_func(f"System {self.region} is already ramping.", "warning")
                return
            
            if self._logic_state == TISystemLogicState.IDLE:
                self._status_update_func(f"System {self.region} is already stopped.", "info")
                return

            self._status_update_func(f"Stopping system {self.region}...", "info")
            self._logic_state = TISystemLogicState.RAMPING_DOWN
            
            self._trigger_event.clear()
            
            self._ramp_thread = threading.Thread(
                target=self._threaded_stop_task,
                daemon=True
            )
            self._ramp_thread.start()
    
    def _threaded_stop_task(self) -> None:
        """[THREAD-TARGET] Contains the blocking logic for ramp-down and shutdown."""
        try:
            # 1. Ramp down to 0V (blocking part)
            target_voltages_for_ramp = {
                key: 0.0 for key in self.channels
            }
            ramp_durations = {
                key: ch.ramp_duration_s for key, ch in self.channels.items()
            }
            self.ramp(target_voltages_for_ramp, ramp_durations)
            
            # 2. Ensure outputs are off (Concurrent)
            if not self._trigger_event.is_set():
                num_channels = len(self.channels)
                with concurrent.futures.ThreadPoolExecutor(max_workers=num_channels) as executor:
                    futures = [
                        executor.submit(channel.set_output_state, OutputState.OFF)
                        for channel in self.channels.values()
                    ]
                    concurrent.futures.wait(futures)
                    for future in futures:
                        future.result() # Re-raises exceptions
                        
                self._status_update_func(f"System {self.region} stopped.", "success")
                with self._state_lock:
                    self._logic_state = TISystemLogicState.IDLE
            else:
                self._status_update_func(f"System {self.region} stop was interrupted.", "warning")
                with self._state_lock:
                    if self._logic_state != TISystemLogicState.ERROR:
                        self._logic_state = TISystemLogicState.IDLE
                
        except Exception as e:
            logger.error(f"Failed to turn off outputs for {self.region}: {e}", exc_info=True)
            self._status_update_func(f"Error stopping {self.region}: {e}", "error")
            with self._state_lock:
                self._logic_state = TISystemLogicState.ERROR
            self.emergency_stop() 
        
        finally:
            with self._state_lock:
                self._ramp_thread = None
            
            self._trigger_event.clear()

    # --- ramp_channel_voltage methods (MODIFIED) ---
    def ramp_channel_voltage(self, channel_key: str, target_voltage: float, rate_v_per_s: float = 0.1) -> None:
        """
        Starts a non-blocking ramp for a *single* channel (by key) to a
        target voltage at a specified rate (V/s).
        All other channels are held at their current voltage.
        
        This method will wait for a hardware trigger before ramping.
        """
        if channel_key not in self.channels:
            self._status_update_func(f"Invalid channel key '{channel_key}'.", "error")
            logger.error(f"ramp_channel_voltage: Invalid channel key {channel_key}.")
            return
            
        if rate_v_per_s <= 0:
            self._status_update_func(f"Ramp rate must be positive, not {rate_v_per_s} V/s.", "error")
            logger.error(f"ramp_channel_voltage: Invalid rate {rate_v_per_s}.")
            return

        with self._state_lock:
            if self.is_ramping:
                self._status_update_func(f"System {self.region} is already ramping.", "warning")
                return
            
            if self._logic_state == TISystemLogicState.ERROR:
                 self._status_update_func(f"System {self.region} is in ERROR state. Cannot ramp.", "warning")
                 return

            self._status_update_func(f"Ramping {channel_key} for {self.region}...", "info")
            
            self._trigger_event.clear()
            # MODIFICATION: Set state to WAITING_FOR_TRIGGER
            self._logic_state = TISystemLogicState.WAITING_FOR_TRIGGER
            
            self._ramp_thread = threading.Thread(
                target=self._threaded_ramp_single_channel_task,
                args=(channel_key, target_voltage, rate_v_per_s),
                daemon=True
            )
            self._ramp_thread.start()

    def _threaded_ramp_single_channel_task(self, channel_key: str, target_voltage: float, rate_v_per_s: float) -> None:
        """
        [THREAD-TARGET] Contains the blocking logic for a single channel
        voltage ramp, including the trigger-wait.
        """
        try:
            # --- MODIFICATION: Wait for hardware enabling and trigger ---
            if not self._trigger_event.is_set():
                _hw_manager: HardwareManager = next(iter(self.channels.values())).hw_manager
                trigger_event = _hw_manager.trigger_event
                
                # State is already WAITING_FOR_TRIGGER (set by ramp_channel_voltage())
                self._status_update_func(f"System {self.region} (for {channel_key} ramp) outputs enabled. Waiting for hardware trigger...", "info")
                logger.info(f"System {self.region} (for {channel_key} ramp) waiting for hardware trigger event...")
                
                # This call blocks until the event is set by HardwareManager.send_software_trigger()
                trigger_event.wait()
                
                if self._trigger_event.is_set():
                     logger.warning(f"System {self.region} stop event triggered while waiting for trigger.")
                     raise Exception("Stop event triggered during trigger wait")
                
                # --- MODIFIED: Transition state from WAITING to RAMPING_INTERMEDIATE ---
                with self._state_lock:
                    # Check again in case stop was called right after wait() but before lock
                    if self._trigger_event.is_set():
                         raise Exception("Stop event triggered immediately after trigger wait")
                    self._logic_state = TISystemLogicState.RAMPING_INTERMEDIATE
                # --- END MODIFICATION ---
                
                logger.info(f"System {self.region} hardware trigger event received. Starting single-channel ramp for {channel_key}.")
                self._status_update_func(f"System {self.region} trigger received. Ramping {channel_key}...", "info")
            # --- END MODIFICATION ---

            # 1. Get ramping channel and calculate duration
            ramping_channel = self.channels[channel_key]
            start_v_ramp = ramping_channel.get_current_voltage()
            
            delta_v = abs(target_voltage - start_v_ramp)
            duration_s = 0.0
            if rate_v_per_s > 0:
                duration_s = delta_v / rate_v_per_s
            
            # 2. Define ramp parameters for ALL channels
            target_voltages: Dict[str, float] = {}
            durations: Dict[str, float] = {}
            
            other_channels_info = []

            for key, ch in self.channels.items():
                if key == channel_key:
                    target_voltages[key] = target_voltage
                    durations[key] = duration_s
                else:
                    current_v = ch.get_current_voltage()
                    target_voltages[key] = current_v
                    durations[key] = 0.0
                    other_channels_info.append(f"{key} at {current_v:.2f}V")

            self._status_update_func(
                f"Region {self.region}: Ramping {channel_key} from {start_v_ramp:.2f}V to {target_voltage:.2f}V "
                f"({duration_s:.2f}s). Holding: [{', '.join(other_channels_info)}].", 
                "info"
            )
            
            # 3. Execute the ramp (blocking part)
            self.ramp(target_voltages, durations)
            
            # 4. Update state on success
            with self._state_lock:
                if not self._trigger_event.is_set():
                    all_at_target = True
                    all_at_zero = True
                    
                    for key, ch in self.channels.items():
                        v = ch.get_current_voltage()
                        t = ch.target_voltage
                        
                        if abs(v - t) > 1e-6:
                            all_at_target = False
                        if abs(v) > 1e-6:
                            all_at_zero = False
                    
                    if all_at_target:
                        self._logic_state = TISystemLogicState.RUNNING_AT_TARGET
                        self._status_update_func(f"System {self.region} is running at target.", "success")
                    elif all_at_zero:
                        self._logic_state = TISystemLogicState.IDLE
                        self._status_update_func(f"System {self.region} stopped.", "success")
                    else:
                        self._logic_state = TISystemLogicState.RUNNING_INTERMEDIATE
                        self._status_update_func(f"System {self.region} at custom voltage.", "info")
                else:
                    self._logic_state = TISystemLogicState.IDLE
                    
        except Exception as e:
            if not self._trigger_event.is_set():
                # Only log as error if it wasn't a deliberate stop
                error_msg = f"Failed to ramp channel {channel_key} for TISystem {self.region}: {e}"
                logger.error(error_msg, exc_info=True)
                self._status_update_func(f"Error ramping {channel_key} ({self.region}): {e}", "error")
                with self._state_lock:
                    self._logic_state = TISystemLogicState.ERROR
            else:
                logger.warning(f"TISystem {self.region} ramp task was interrupted by stop event.")
                with self._state_lock:
                    self._logic_state = TISystemLogicState.IDLE

            self.emergency_stop()
        finally:
            with self._state_lock:
                self._ramp_thread = None

    # --- emergency_stop (Unchanged) ---
    def emergency_stop(self) -> None:
        """
        Immediately sets all channel amplitudes to 0V and turns outputs off.
        Bypasses any ramp and interrupts any active ramp thread.
        Thread-safe.
        """
        self._trigger_event.set()
        
        with self._state_lock:
            self._logic_state = TISystemLogicState.ERROR
        
        self._status_update_func(f"EMERGENCY STOP triggered for {self.region}", "error")
        logger.warning(f"EMERGENCY STOP triggered for {self.region}")
        
        try:
            # MODIFICATION: Use a concurrent stop for speed
            num_channels = len(self.channels)
            with concurrent.futures.ThreadPoolExecutor(max_workers=num_channels) as executor:
                futures = [
                    executor.submit(channel.immediate_stop)
                    for channel in self.channels.values()
                ]
                concurrent.futures.wait(futures)
                for future in futures:
                    if future.exception():
                        logger.error(f"Error during channel immediate_stop: {future.exception()}")
            
        except Exception as e:
            logger.error(f"Error during emergency stop for {self.region}: {e}", exc_info=True)
            self._status_update_func(f"Critical error during e-stop {self.region}: {e}", "error")

    # --- _calculate_trajectories (Unchanged) ---
    def _calculate_trajectories(self, 
                                target_voltages: Dict[str, float], 
                                duration_secs: Dict[str, float]
                               ) -> Tuple[Dict[str, np.ndarray], int]:
        """
        Calculates voltage trajectories for all channels based on current state.
        This method is thread-safe.
        """
        
        trajectories: Dict[str, np.ndarray] = {}
        num_steps_dict: Dict[str, int] = {}

        if not self.channels:
            return {}, 0
        
        for key, channel in self.channels.items():
            start_v = channel.get_current_voltage()
            target_v = max(0.0, target_voltages.get(key, start_v))
            duration_s = max(0.0, duration_secs.get(key, 0.0))

            num_steps = 0
            if duration_s == 0.0:
                num_steps = 2
            else:
                num_steps = int(duration_s / self.ramp_time_step_s)
                if num_steps < 2:
                    num_steps = 2
            
            num_steps_dict[key] = num_steps
            
            if num_steps == 2 and duration_s == 0.0:
                trajectories[key] = np.array([start_v, start_v])
            else:
                trajectories[key] = np.linspace(start_v, target_v, num_steps)
        
        num_steps_total = max(num_steps_dict.values()) if num_steps_dict else 0
        
        return trajectories, num_steps_total

    # --- ramp (Unchanged) ---
    def ramp(self, target_voltages: Dict[str, float], duration_secs: Dict[str, float]) -> None:
        """
        Calculates voltage trajectories and executes the (blocking) ramp.
        This method is now intended to be called by the threaded tasks.
        """
        (trajectories, 
         num_steps_total) = self._calculate_trajectories(target_voltages, 
                                                          duration_secs)
        
        if num_steps_total == 0:
            logger.warning(f"Ramp for {self.region} called with no channels or 0 steps.")
            return

        try:
            self._execute_ramp(trajectories, num_steps_total, self.ramp_time_step_s)
        except KeyboardInterrupt:
            logger.warning(f"Ramp for {self.region} interrupted by user (KeyboardInterrupt).")
            self._status_update_func("Ramp interrupted by user.", "warning")
            self.emergency_stop()
        except Exception as e:
            logger.error(f"Unhandled exception in {self.region} ramp execution: {e}", exc_info=True)
            self._status_update_func(f"Runtime error in ramp: {e}", "error")
            self.emergency_stop()
            raise
            
    # --- _execute_ramp (Unchanged) ---
    def _execute_ramp(self, trajectories: Dict[str, np.ndarray], num_steps_total: int, time_step_s: float) -> None:
        """     
        Contains the core loop for executing the voltage ramp.
        This method is interruptible by _trigger_event and now uses a
        ThreadPoolExecutor to set all channel voltages concurrently.
        """
        
        traj_lengths = {key: len(traj) for key, traj in trajectories.items()}
        start_time = time.time()
        time_step_s = max(0.0, time_step_s) 
        num_channels = len(self.channels)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_channels) as executor:
            try:
                for i in range(num_steps_total):
                    
                    if self._trigger_event.is_set():
                        self._status_update_func("Ramp interrupted by stop event.", "warning")
                        logger.warning(f"{self.region}: Ramp interrupted by stop event.")
                        break

                    step_start_time = time.perf_counter()
                    
                    futures = []
                    for key, channel in self.channels.items():
                        traj = trajectories[key]
                        num_steps_ch = traj_lengths[key]
                        
                        v = traj[i] if i < num_steps_ch else traj[-1]
                        
                        futures.append(executor.submit(channel.set_amplitude, v))
                    
                    done, not_done = concurrent.futures.wait(futures)
                    
                    for future in done:
                        if future.exception():
                            raise future.exception()

                    progress = (i + 1) / num_steps_total * 100
                    if self._progress_callback:
                        try:
                            self._progress_callback(self.region, progress)
                        except Exception as e:
                            logger.warning(f"Progress callback for {self.region} failed: {e}")

                    if time_step_s > 0:
                        elapsed_step = time.perf_counter() - step_start_time
                        sleep_time = max(0, time_step_s - elapsed_step)
                        time.sleep(sleep_time)

                if not self._trigger_event.is_set():
                    final_voltages_str_list = []
                    
                    if self._progress_callback:
                        self._progress_callback(self.region, 100.0)

                    futures = []
                    for key, channel in self.channels.items():
                        final_v = trajectories[key][-1]
                        futures.append(executor.submit(channel.set_amplitude, final_v))
                    
                    concurrent.futures.wait(futures)
                    
                    for future, (key, channel) in zip(futures, self.channels.items()):
                        if future.exception():
                            raise future.exception()
                        
                        final_voltages_str_list.append(
                             f"{key}: {channel.get_current_voltage():.2f}V"
                        )
                        
                    final_voltages_str = ", ".join(final_voltages_str_list)
                    logger.info(f"{self.region}: Ramp finished in {time.time() - start_time:.2f}s. Final Voltages: [{final_voltages_str}]")
                    self._status_update_func(f"Ramp finished. Voltages: [{final_voltages_str}]", "success")

                else: 
                    current_voltages_str_list = []
                    for key, channel in self.channels.items():
                        current_voltages_str_list.append(
                            f"{key}: {channel.get_current_voltage():.2f}V"
                        )
                    
                    current_voltages_str = ", ".join(current_voltages_str_list)
                    self._status_update_func(f"Ramp stopped prematurely. Current Voltages: [{current_voltages_str}]", "warning")
                    logger.warning(f"{self.region}: Ramp stopped prematurely. Voltages left at: [{current_voltages_str}]")

            except Exception as e:
                logger.error(f"Error setting voltage during step {i}: {e}", exc_info=True)
                self._status_update_func(f"Hardware Error setting voltage: {e}", "error")
                self.emergency_stop()
                return
            
            finally:
                if self._progress_callback == self._default_progress_update:
                    sys.stdout.write('\r\033[K')
                    sys.stdout.flush()