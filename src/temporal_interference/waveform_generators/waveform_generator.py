from abc import ABC, abstractmethod
from enum import Enum
from typing import Type, Optional, Any, Dict

# ======================================================================================
# Helper Enumerations for a Type-Safe API
# ======================================================================================

class OutputState(Enum):
    """Defines the possible output states for a generator channel."""
    ON = 'ON'
    OFF = 'OFF'

class WaveformShape(Enum):
    """Defines standard waveform shapes supported by function generators."""
    SINE = 'SIN'
    SQUARE = 'SQU'
    RAMP = 'RAMP'
    PULSE = 'PULS'
    ARBITRARY = 'ARB'

# ======================================================================================
# Cohesive Abstract Base Class
# ======================================================================================

class AbstractWaveformGenerator(ABC):
    """
    Abstract Base Class for a signal/waveform generator.

    This class defines a standard interface for instrument control, including
    connection management, channel configuration, and status reporting. It is
    designed to be used as a context manager to ensure proper resource handling.
    """

    def __init__(self, resource_id: str, **kwargs: Any) -> None:
        """
        Initializes the generator with a specific hardware resource identifier.

        Args:
            resource_id (str): The identifier for the hardware device,
                               e.g., a VISA address like 'GPIB0::10::INSTR'.
            **kwargs: Additional device-specific configuration parameters.
        """
        self.resource_id = resource_id
        # Concrete implementations can handle kwargs for custom setup.

    # --- Connection Management (Context Manager) ---

    @abstractmethod
    def connect(self) -> None:
        """
        Establishes a connection to the hardware device.
        Should raise an exception on failure.
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Closes the connection to the hardware device and performs cleanup."""
        pass

    def __enter__(self) -> 'AbstractWaveformGenerator':
        """Context manager entry point: connects to the device."""
        self.connect()
        return self

    def __exit__(self,
                 exc_type: Optional[Type[BaseException]],
                 exc_value: Optional[BaseException],
                 traceback: Optional[Any]) -> None:
        """Context manager exit point: disconnects from the device."""
        self.disconnect()

    # --- Instrument Status ---

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """
        Returns a dictionary containing the current status of the hardware.
        e.g., {'connection': 'active', 'channel_1_output': 'ON'}.
        """
        pass

    # --- Low-Level Channel Configuration ---
    @abstractmethod
    def set_output_state(self, channel: int, state: OutputState) -> None:
        """
        Enables or disables a specific output channel.

        Args:
            channel (int): The channel number (e.g., 1, 2).
            state (OutputState): The desired output state (ON or OFF).
        """
        pass

    @abstractmethod
    def set_frequency(self, channel: int, frequency: float) -> None:
        """
        Sets the frequency for a specific channel.

        Args:
            channel (int): The channel number.
            frequency (float): The frequency in Hertz (Hz).
        """
        pass

    @abstractmethod
    def set_amplitude(self, channel: int, amplitude: float) -> None:
        """
        Sets the voltage amplitude for a specific channel.

        Args:
            channel (int): The channel number.
            amplitude (float): The peak-to-peak voltage amplitude (Vpp).
        """
        pass
        
    @abstractmethod
    def set_offset(self, channel: int, offset: float) -> None:
        """
        Sets the DC voltage offset for a specific channel.

        Args:
            channel (int): The channel number.
            offset (float): The DC offset in Volts (V).
        """
        pass

    @abstractmethod
    def set_waveform_shape(self, channel: int, shape: WaveformShape) -> None:
        """
        Sets the waveform shape for a specific channel.

        Args:
            channel (int): The channel number.
            shape (WaveformShape): The desired waveform shape (e.g., SINE, SQUARE).
        """
        pass

    # --- High-Level Convenience Method ---
    
    def apply_waveform(self,
                         channel: int,
                         shape: WaveformShape,
                         frequency: float,
                         amplitude: float,
                         offset: float = 0.0) -> None:
        """
        A convenience method to configure and apply a standard waveform to a channel.

        This default implementation calls the low-level setters sequentially.
        Concrete classes can override this method for hardware that supports
        atomic updates for better performance.

        Args:
            channel (int): The channel number.
            shape (WaveformShape): The waveform shape.
            frequency (float): The frequency in Hertz (Hz).
            amplitude (float): The voltage amplitude (Vpp).
            offset (float, optional): The DC offset in Volts (V). Defaults to 0.0.
        """
        self.set_waveform_shape(channel, shape)
        self.set_frequency(channel, frequency)
        self.set_amplitude(channel, amplitude)
        self.set_offset(channel, offset)
        self.set_output_state(channel, OutputState.ON)