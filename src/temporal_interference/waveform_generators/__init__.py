import os
import logging
from typing import Any

# Import the base class (which has the registry)
from .waveform_generator import AbstractWaveformGenerator, WaveformShape

# --- CRITICAL STEP ---
# You must import all driver modules you want to be available in the factory.
# This import statement is what triggers the __init_subclass__ registration.
from .keysight_edu33212A import KeysightEDU33212A 

log = logging.getLogger(__name__)

def create_waveform_generator(
    model: str, 
    resource_id: str, 
    **kwargs: Any
) -> AbstractWaveformGenerator:
    """
    Factory function to create a waveform generator instance from a model string.

    Args:
        model (str): The model_id string (e.g., "KeysightEDU33212A").
        resource_id (str): The VISA resource ID (e.g., "GPIB0::10::INSTR").
        **kwargs: Additional keyword arguments to pass to the driver's
                  constructor (e.g., name, timeout).

    Returns:
        AbstractWaveformGenerator: An initialized instance of the correct concrete driver.
    """
    log.info(f"Attempting to create generator for model: '{model}' at {resource_id}")
    
    # 1. Get the correct class from the registry
    try:
        driver_class = AbstractWaveformGenerator.get_driver_class(model)
    except ValueError as e:
        log.error(f"Factory creation failed: {e}")
        raise
        
    log.info(f"Found driver class: {driver_class.__name__}")

    # 2. Create and return an instance of that class
    # The resource_id is passed, along with any other driver-specific settings
    return driver_class(resource_id=resource_id, **kwargs)


# This list defines what symbols are imported when a user types:
__all__ = [
    # The factory function
    "create_waveform_generator",
    
    # Public base class
    "AbstractWaveformGenerator",
    
    # Public enums
    "OutputState",
    "WaveformShape"
]