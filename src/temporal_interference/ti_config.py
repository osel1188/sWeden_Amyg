# ti_config.py

import json
import logging
from typing import Dict, List

class TIConfig:
    """
    Manages the temporal interference (TI) stimulation configuration.
    """
    def __init__(self, config_path: str = 'ti_config.json'):
        """
        Initializes the TIConfig class.

        Args:
            config_path (str): Path to the JSON configuration file.
        """
        # This line initiates the loading and processing of the configuration file.
        self.config = self._load_config(config_path)
        if not self.config:
             raise ValueError("Failed to load or validate the configuration file.")
        
    def _validate_config(self, config: Dict) -> None:
        """
        Validates the structure and presence of essential keys in the configuration.

        Args:
            config (Dict): The loaded configuration dictionary.
        
        Raises:
            ValueError: If a required key is missing.
        """
        # Define the required top-level keys
        required_top_level_keys: List[str] = ['hardware', 'waveform_generator_config', 'protocols']
        for key in required_top_level_keys:
            if key not in config:
                raise ValueError(f"Configuration missing required top-level key: '{key}'")

        # Validate nested structure of 'hardware'
        required_hardware_keys: List[str] = ['waveform_generators', 'electrodes', 'ti_systems']
        for key in required_hardware_keys:
             if key not in config.get('hardware', {}):
                  raise ValueError(f"Configuration missing required key in 'hardware': '{key}'")

        # Validate nested structure of 'waveform_generator_config'
        required_wg_config_keys: List[str] = ['default', 'safety_limits', 'waveform_generator_presets_assignments']
        for key in required_wg_config_keys:
             if key not in config.get('waveform_generator_config', {}):
                  raise ValueError(f"Configuration missing required key in 'waveform_generator_config': '{key}'")
        
        # Validate that 'protocols' is not empty
        if not config.get('protocols'):
            raise ValueError("The 'protocols' dictionary cannot be empty.")

    def _load_config(self, config_path: str) -> Dict | None:
        """
        Loads and validates the configuration from a JSON file.

        Args:
            config_path (str): The path to the JSON configuration file.
        
        Returns:
            Dict | None: The loaded configuration dictionary, or None if an error occurs.
        """
        try:
            # File I/O: Opens and reads the JSON file from the specified path.
            with open(config_path, 'r') as f:
                config: Dict = json.load(f)
            logging.info(f"Configuration loaded successfully from {config_path}")
            
            # Content Management (Validation): Checks for the presence of essential keys.
            self._validate_config(config)
            
            return config
        
        # Error handling for file I/O, parsing, and validation.
        except FileNotFoundError:
            logging.error(f"Configuration file not found: {config_path}")
            return None
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON configuration file {config_path}: {e}")
            return None
        except ValueError as e:
            logging.error(f"Configuration validation failed: {e}")
            return None
        except Exception as e:
            logging.error(f"An unexpected error occurred loading config {config_path}: {e}")
            return None
        
