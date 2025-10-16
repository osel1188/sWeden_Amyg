import importlib
from typing import Dict
from .waveform_generator import AbstractWaveformGenerator

def create_waveform_generator(config: Dict) -> AbstractWaveformGenerator:
    """
    Factory function to dynamically load and instantiate a waveform generator.
    """
    module_name = config['module']
    class_name = config['class']
    params = config.get('params', {})
    
    try:
        # Dynamically import the specified module from the 'generators' submodule
        generator_module = importlib.import_module(f".generators.{module_name}", package='ti_system.hardware')
        # Get the class from the imported module
        generator_class = getattr(generator_module, class_name)
        # Instantiate the class with its parameters
        instance = generator_class(**params)
        return instance
    except (ImportError, AttributeError) as e:
        raise ValueError(f"Failed to load waveform generator '{class_name}' from module '{module_name}': {e}")