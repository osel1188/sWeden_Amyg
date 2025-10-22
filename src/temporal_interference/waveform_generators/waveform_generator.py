from abc import ABC, abstractmethod
from enum import Enum
from typing import Type, Optional, Any, Dict, TypeVar

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

class TriggerSource(Enum):
    """Defines standard trigger sources."""
    BUS = 'BUS'        # Software/Internal Trigger
    EXTERNAL = 'EXT'   # External Hardware Trigger

# ======================================================================================
# Cohesive Abstract Base Class
# ======================================================================================

# Type variable for the factory
T_Generator = TypeVar('T_Generator', bound='AbstractWaveformGenerator')

class AbstractWaveformGenerator(ABC):
    """
    Abstract Base Class for a signal/waveform generator.
        
    This class defines a standard interface for instrument control, including
    connection management, channel configuration, and status reporting. It is
    designed to be used as a context manager to ensure proper resource handling.
    """
    
    # --- Class-level Registry for Factory Pattern ---
    # This dictionary will map model_id strings to the class itself.
    _driver_registry: Dict[str, Type[T_Generator]] = {}

    def __init_subclass__(cls, *, model_id: str, **kwargs: Any) -> None:
        """
        Magic method to automatically register any subclass.
        
        When a new class inherits from AbstractWaveformGenerator and provides
        a 'model_id' keyword argument in its class definition, it will be
        automatically added to the registry.
        
        Example:
            class MyDriver(AbstractWaveformGenerator, model_id="my_driver_id"):
                ...
        """
        super().__init_subclass__(**kwargs)
        if model_id in cls._driver_registry:
            raise ValueError(
                f"Error: Duplicate model_id '{model_id}' attempting to "
                f"register class {cls.__name__}. "
                f"Already registered to {cls._driver_registry[model_id].__name__}."
            )
        cls._driver_registry[model_id] = cls
        cls.model = model_id
        # print(f"Registered driver: {model_id} -> {cls.__name__}") # Optional: for debugging
        

    def __init__(self, resource_id: str, **kwargs: Any) -> None:
        """
        Initializes the generator with a specific hardware resource identifier.
        ... [rest of init method] ...
        """
        self.resource_id = resource_id
        # Concrete implementations can handle kwargs for custom setup.

    # --- Factory Accessor Method (Static) ---
    
    @staticmethod
    def get_registered_drivers() -> Dict[str, Type[T_Generator]]:
        """Returns a copy of the driver registry."""
        return AbstractWaveformGenerator._driver_registry.copy()
        
    @staticmethod
    def get_driver_class(model_id: str) -> Type[T_Generator]:
        """
        Looks up and returns a driver class from the registry.
        
        Note: This requires the module containing the driver to have been
        imported at least once to trigger registration.
        """
        try:
            return AbstractWaveformGenerator._driver_registry[model_id]
        except KeyError:
            raise ValueError(
                f"No driver registered with model_id: '{model_id}'. "
                f"Available drivers: {list(AbstractWaveformGenerator._driver_registry.keys())}"
            )

    # --- Connection Management (Context Manager) ---
    
    @abstractmethod
    def connect(self) -> None:
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass

    def __enter__(self) -> 'AbstractWaveformGenerator':
        self.connect()
        return self

    def __exit__(self,
                 exc_type: Optional[Type[BaseException]],
                 exc_value: Optional[BaseException],
                 traceback: Optional[Any]) -> None:
        self.disconnect()
    
    # --- Instrument Status ---

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """
        Returns a dictionary containing the current status of the hardware.
        e.g., {'connection': 'active', 'channel_1_output': 'ON'}.
        """
        pass

    # --- Low-Level Channel Configuration (Setters) ---
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

    # --- Low-Level Channel Configuration (Getters) ---
    
    @abstractmethod
    def get_frequency(self, channel: int) -> float:
        """
        Queries the frequency of a specific channel.

        Args:
            channel (int): The channel number.
        
        Returns:
            float: The frequency in Hertz (Hz).
        """
        pass

    @abstractmethod
    def get_amplitude(self, channel: int) -> float:
        """
        Queries the peak-to-peak voltage amplitude (Vpp) of a specific channel.

        Args:
            channel (int): The channel number.
            
        Returns:
            float: The peak-to-peak voltage amplitude (Vpp).
        """
        pass

    @abstractmethod
    def get_offset(self, channel: int) -> float:
        """
        Queries the DC offset voltage of a specific channel.

        Args:
            channel (int): The channel number.
            
        Returns:
            float: The DC offset in Volts (V).
        """
        pass

    # --- High-Level and Utility Methods ---
    
    @abstractmethod
    def initialize_device_settings(self, config: Dict[str, Any]) -> None:
        """
        Applies a dictionary of settings to the instrument.
        
        Args:
            config (Dict[str, Any]): A configuration dictionary.
        """
        pass

    @abstractmethod
    def set_trigger_source_bus(self, channel: int) -> None:
        """
        Sets the trigger source to BUS (software/internal) for a specific channel.

        Args:
            channel (int): The channel number.
        """
        pass

    @abstractmethod
    def set_trigger_source_external(self, channel: int) -> None:
        """
        Sets the trigger source to EXT (external hardware trigger) for a specific channel.

        Args:
            channel (int): The channel number.
        """
        pass
        
    @abstractmethod
    def trigger(self) -> None:
        """
        Sends a software trigger to the instrument.
        """
        pass

    @abstractmethod
    def abort(self) -> None:
        """
        Aborts the current waveform generation and returns to an idle state.
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