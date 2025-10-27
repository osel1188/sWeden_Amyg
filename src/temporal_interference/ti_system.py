# ti_system.py (REFACTORED)
#
# This class is re-architected to be independent of the number of channels.
# It operates on the `self.channels: dict[str, TIChannel]` provided
# during initialization, rather than assuming 'channel_1' and 'channel_2'.

import logging
import sys
import time
import threading
from enum import Enum, auto
from typing import List, Callable, Tuple, Optional, Dict
import numpy as np

# Local imports (assumed)
from .ti_channel import TIChannel
from .waveform_generators.waveform_generator import (
    OutputState
)

# --- Define the module-level logger ---
logger = logging.getLogger(__name__)

# --- TISystemLogicState Enum (MODIFIED) ---
class TISystemLogicState(Enum):
    """Defines the discrete operational *logic* states of the TISystem."""
    IDLE = auto()
    RAMPING_UP = auto()
    RUNNING_AT_TARGET = auto()
    RAMPING_DOWN = auto()
    RAMPING_INTERMEDIATE = auto()
    RUNNING_INTERMEDIATE = auto()
    ERROR = auto()

# --- TISystemHardwareState Enum (NEW) ---
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
        
        # --- Callbacks for Decoupling ---
        self._status_update_func: Callable[[str, str], None] = status_update_func or self._default_status_update
        self._progress_callback: Optional[Callable[[str, float], None]] = progress_callback or self._default_progress_update
        self._spinner = ['◜', '◝', '◞', '◟']

        # --- State Management (MODIFIED) ---
        self._logic_state: TISystemLogicState = TISystemLogicState.IDLE
        self._state_lock = threading.RLock()
        self._ramp_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event() 

        # --- Encapsulated Channels ---
        # The system's behavior is now driven by this dictionary
        self.channels: Dict[str, TIChannel] = channels
        
        # --- Operational Parameters ---
        self.ramp_time_step_s: float = 0.02 # 50 Hz

    def _default_status_update(self, message: str, level: str):
        """Default status handler if none is provided."""
        log_level = getattr(logging, level.upper(), logging.INFO)
        logger.log(log_level, f"TISystem ({self.region}): {message}")

    def _default_progress_update(self, region_name: str, progress: float):
        """Default progress handler (console spinner) if none is provided."""
        if progress < 100.0:
            spinner_char = self._spinner[int(time.time() * 10) % 4]
            sys.stdout.write(f'\r\033[K Ramping {region_name} ... {spinner_char} {progress:.1f}%')
        else:
            sys.stdout.write(f'\r\033[K Ramping {region_name} ... Done. 100.0% \n')
        sys.stdout.flush()

    @property
    def logic_state(self) -> TISystemLogicState:
        """Returns the current *intended* operational state of the system."""
        with self._state_lock:
            return self._logic_state

    # --- Hardware State Property ---
    @property
    def hardware_state(self) -> TISystemHardwareState:
        """
        Queries the actual hardware state by checking device amplitudes.
        Returns RUNNING if any channel voltage is non-zero, IDLE otherwise.
        This performs live I/O and may be slow.
        """
        # Note: This checks the *actual* hardware via the generator,
        # not the TIChannel's cached `_current_voltage` state.
        try:
            for channel in self.channels.values():
                # Direct hardware query
                voltage = channel.generator.get_amplitude(channel.wavegen_channel)
                
                # Use a small tolerance for floating point comparison
                if abs(voltage) > 1e-6:
                    return TISystemHardwareState.RUNNING
                    
            # All channels must be at 0.0
            return TISystemHardwareState.IDLE
            
        except Exception as e:
            # Log the error and report an ERROR state
            logger.error(f"Failed to query hardware state for {self.region}: {e}", exc_info=True)
            self._status_update_func(f"Failed to get hardware state: {e}", "error")
            return TISystemHardwareState.ERROR

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

    @property
    def is_ramping(self) -> bool:
        """True if a ramp (up, down, or intermediate) is in progress."""
        with self._state_lock:
            return self._ramp_thread is not None and self._ramp_thread.is_alive()

    @property
    def emergency_stop_triggered(self) -> bool:
        """True if the stop event has been set. Thread-safe."""
        return self._stop_event.is_set()

    # --- Setup methods are now dict-based ---
    
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

    def setup_frequencies(self, frequencies: Dict[str, float]) -> None:
        """Sets the frequency for one or more specified channels."""
        if not self._validate_channel_keys(frequencies, "setup_frequencies"):
            return
            
        log_msgs = []
        for key, freq in frequencies.items():
            self.channels[key].setup_frequency(freq)
            log_msgs.append(f"{key}={freq} Hz")
        logger.info(f"Region {self.region} frequencies set to: {', '.join(log_msgs)}.")

    def setup_ramp_durations(self, durations: Dict[str, float]) -> None:
        """Sets the ramp duration for one or more specified channels."""
        if not self._validate_channel_keys(durations, "setup_ramp_durations"):
            return
            
        log_msgs = []
        for key, dur in durations.items():
            self.channels[key].setup_ramp_duration(dur)
            log_msgs.append(f"{key}={dur}s")
        logger.info(f"Region {self.region} ramp durations set to: {', '.join(log_msgs)}.")

    def setup_ramp_duration(self, duration_s: float) -> None:
        """Sets the same ramp duration for *all* channels."""
        logger.warning("setup_ramp_duration(s) is deprecated. Use setup_ramp_durations(dict) for per-channel control.")
        all_channel_durations = {key: duration_s for key in self.channels}
        self.setup_ramp_durations(all_channel_durations)
    
    def apply_config(self):
        for key in self.channels:
            self.channels[key].apply_config()

    # --- start() is state-aware (logic modified) ---
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
            
            self._stop_event.clear()
            self._logic_state = TISystemLogicState.RAMPING_UP
            
            self._ramp_thread = threading.Thread(
                target=self._threaded_start_task, 
                daemon=True
            )
            self._ramp_thread.start()

    # --- MODIFIED: _threaded_start_task iterates channels and updates logic_state ---
    def _threaded_start_task(self) -> None:
        """[THREAD-TARGET] Contains the blocking logic for setup and ramp-up."""
        try:
            # 1. Configure hardware
            for channel in self.channels.values():
                channel.apply_config()
                channel.set_output_state(OutputState.ON)
            
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
                if not self._stop_event.is_set():
                    self._logic_state = TISystemLogicState.RUNNING_AT_TARGET
                    self._status_update_func(f"System {self.region} is running at target.", "success")
                else:
                    self._logic_state = TISystemLogicState.IDLE
                    
        except Exception as e:
            error_msg = f"Failed to start TISystem {self.region}: {e}"
            logger.error(error_msg, exc_info=True)
            self._status_update_func(f"Error starting {self.region}: {e}", "error")
            with self._state_lock:
                self._logic_state = TISystemLogicState.ERROR
            self.emergency_stop()
        finally:
            with self._state_lock:
                self._ramp_thread = None

    # --- stop() is state-aware (logic modified) ---
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
            
            self._stop_event.clear()
            
            self._ramp_thread = threading.Thread(
                target=self._threaded_stop_task,
                daemon=True
            )
            self._ramp_thread.start()
    
    # --- MODIFIED: _threaded_stop_task iterates channels and updates logic_state ---
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
            
            # 2. Ensure outputs are off
            if not self._stop_event.is_set():
                for channel in self.channels.values():
                    channel.set_output_state(OutputState.OFF)
                    
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
            
            self._stop_event.clear()

    # --- MODIFIED: ramp_channel_voltage accepts channel_key: str, updates logic_state ---
    def ramp_channel_voltage(self, channel_key: str, target_voltage: float, rate_v_per_s: float = 0.1) -> None:
        """
        Starts a non-blocking ramp for a *single* channel (by key) to a
        target voltage at a specified rate (V/s).
        All other channels are held at their current voltage.
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
            
            self._stop_event.clear()
            self._logic_state = TISystemLogicState.RAMPING_INTERMEDIATE
            
            self._ramp_thread = threading.Thread(
                target=self._threaded_ramp_single_channel_task,
                args=(channel_key, target_voltage, rate_v_per_s),
                daemon=True
            )
            self._ramp_thread.start()

    # --- _threaded_ramp_single_channel_task is N-channel aware, updates logic_state ---
    def _threaded_ramp_single_channel_task(self, channel_key: str, target_voltage: float, rate_v_per_s: float) -> None:
        """
        [THREAD-TARGET] Contains the blocking logic for a single channel
        voltage ramp.
        """
        try:
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
                    # Hold other channels at their current voltage
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
                if not self._stop_event.is_set():
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
            error_msg = f"Failed to ramp channel {channel_key} for TISystem {self.region}: {e}"
            logger.error(error_msg, exc_info=True)
            self._status_update_func(f"Error ramping {channel_key} ({self.region}): {e}", "error")
            with self._state_lock:
                self._logic_state = TISystemLogicState.ERROR
            self.emergency_stop()
        finally:
            with self._state_lock:
                self._ramp_thread = None

    # --- E-Stop iterates channels, updates logic_state ---
    def emergency_stop(self) -> None:
        """
        Immediately sets all channel amplitudes to 0V and turns outputs off.
        Bypasses any ramp and interrupts any active ramp thread.
        Thread-safe.
        """
        self._stop_event.set()
        
        with self._state_lock:
            self._logic_state = TISystemLogicState.ERROR
        
        self._status_update_func(f"EMERGENCY STOP triggered for {self.region}", "error")
        logger.warning(f"EMERGENCY STOP triggered for {self.region}")
        
        try:
            for channel in self.channels.values():
                channel.immediate_stop()
        except Exception as e:
            logger.error(f"Error during emergency stop for {self.region}: {e}", exc_info=True)
            self._status_update_func(f"Critical error during e-stop {self.region}: {e}", "error")

    # --- _calculate_trajectories is N-channel aware ---
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
            # Get start voltage from channel state (thread-safe)
            start_v = channel.get_current_voltage()
            
            # Default to current voltage if key is missing
            target_v = max(0.0, target_voltages.get(key, start_v))
            
            # Default to 0.0s duration if key is missing
            duration_s = max(0.0, duration_secs.get(key, 0.0))

            # Calculate steps for this channel
            num_steps = 0
            if duration_s == 0.0:
                num_steps = 2 # At least 2 steps for start/end
            else:
                num_steps = int(duration_s / self.ramp_time_step_s)
                if num_steps < 2:
                    num_steps = 2
            
            num_steps_dict[key] = num_steps
            
            # Handle the 0.0 duration case explicitly for holding voltage
            if num_steps == 2 and duration_s == 0.0:
                trajectories[key] = np.array([start_v, start_v])
            else:
                trajectories[key] = np.linspace(start_v, target_v, num_steps)
        
        num_steps_total = max(num_steps_dict.values()) if num_steps_dict else 0
        
        return trajectories, num_steps_total

    # --- ramp() takes dicts ---
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
            
    # --- _execute_ramp() is N-channel aware ---
    def _execute_ramp(self, trajectories: Dict[str, np.ndarray], num_steps_total: int, time_step_s: float) -> None:
        """ 
        Contains the core loop for executing the voltage ramp.
        This method is interruptible by _stop_event.
        """
        
        # Pre-calculate trajectory lengths
        traj_lengths = {key: len(traj) for key, traj in trajectories.items()}
        
        start_time = time.time()
        time_step_s = max(0.0, time_step_s) 

        try:
            for i in range(num_steps_total):
                
                # 1. Check for stop signal
                if self._stop_event.is_set():
                    self._status_update_func("Ramp interrupted by stop event.", "warning")
                    logger.warning(f"{self.region}: Ramp interrupted by stop event.")
                    break

                step_start_time = time.perf_counter()
                
                try:
                    # 2. --- Hardware Interaction via Channel ---
                    for key, channel in self.channels.items():
                        traj = trajectories[key]
                        num_steps_ch = traj_lengths[key]
                        
                        # Get voltage for this step.
                        # If ramp is shorter, hold final value.
                        v = traj[i] if i < num_steps_ch else traj[-1]
                        
                        channel.set_amplitude(v)
                    # ----------------------------------------

                except Exception as e:
                    logger.error(f"Error setting voltage during step {i}: {e}", exc_info=True)
                    self._status_update_func(f"Hardware Error setting voltage: {e}", "error")
                    self.emergency_stop()
                    return

                # 3. --- Progress Reporting (Decoupled) ---
                progress = (i + 1) / num_steps_total * 100
                if self._progress_callback:
                    try:
                        self._progress_callback(self.region, progress)
                    except Exception as e:
                        logger.warning(f"Progress callback for {self.region} failed: {e}")

                # 4. --- Timing ---
                if time_step_s > 0:
                    elapsed_step = time.perf_counter() - step_start_time
                    sleep_time = max(0, time_step_s - elapsed_step)
                    time.sleep(sleep_time)

            # --- Final Step (No system lock) ---
            if not self._stop_event.is_set():
                final_voltages_str_list = []
                
                # Report 100% completion
                if self._progress_callback:
                    self._progress_callback(self.region, 100.0)

                try:
                    # Set final voltages directly to ensure accuracy
                    for key, channel in self.channels.items():
                        final_v = trajectories[key][-1]
                        channel.set_amplitude(final_v)
                        
                        final_voltages_str_list.append(
                             f"{key}: {channel.get_current_voltage():.2f}V"
                        )
                    
                    final_voltages_str = ", ".join(final_voltages_str_list)
                    logger.info(f"{self.region}: Ramp finished in {time.time() - start_time:.2f}s. Final Voltages: [{final_voltages_str}]")
                    self._status_update_func(f"Ramp finished. Voltages: [{final_voltages_str}]", "success")

                except Exception as e:
                    logger.error(f"Error setting final voltage: {e}", exc_info=True)
                    self._status_update_func(f"Hardware Error setting final voltage: {e}", "error")
                    self.emergency_stop()
                    return

            else: 
                # Ramp was stopped prematurely
                current_voltages_str_list = []
                for key, channel in self.channels.items():
                    current_voltages_str_list.append(
                        f"{key}: {channel.get_current_voltage():.2f}V"
                    )
                
                current_voltages_str = ", ".join(current_voltages_str_list)
                self._status_update_func(f"Ramp stopped prematurely. Current Voltages: [{current_voltages_str}]", "warning")
                logger.warning(f"{self.region}: Ramp stopped prematurely. Voltages left at: [{current_voltages_str}]")

        finally:
            # Clear console line if default callback was used
            if self._progress_callback == self._default_progress_update:
                sys.stdout.write('\r\033[K')
                sys.stdout.flush()