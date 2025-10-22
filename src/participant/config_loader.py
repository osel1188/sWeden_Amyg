from pathlib import Path
from typing import Dict, Union

# --- Custom Exceptions for the API ---

class ConfigError(Exception):
    """Errors related to configuration file loading."""
    pass

# --- Concern 1: Configuration Management ---

class ConfigLoader:
    """
    Loads and validates configuration from a key-value text file.
    """
    def __init__(self, config_file_path: Union[str, Path]):
        self.config_file_path = config_file_path
        self.config_paths: Dict[str, str] = {}

    def load_config(self) -> Dict[str, str]:
        """
        Reads the config file and returns a dictionary of paths.
        
        :raises ConfigError: If file not found or keys are missing.
        """
        try:
            with open(self.config_file_path, 'r') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.split('=', 1)
                        self.config_paths[key.strip()] = value.strip()
            
            self._validate_keys()
            return self.config_paths

        except FileNotFoundError:
            raise ConfigError(f"Configuration file not found at: {self.config_file_path}")
        except Exception as e:
            raise ConfigError(f"Error parsing config file: {e}")

    def _validate_keys(self):
        """Ensure required keys are present."""
        # MODIFIED: Renamed 'master_list_file_path'
        required_keys = [
            'condition_file_path', 
            'save_dir_base_path', 
            'participants_list_file_path'
        ]
        missing_keys = [key for key in required_keys if key not in self.config_paths]
        if missing_keys:
            raise ConfigError(f"Missing required keys in config: {', '.join(missing_keys)}")
            
    def get_condition_path(self) -> str:
        return self.config_paths['condition_file_path']
        
    def get_save_dir(self) -> Path:
        return Path(self.config_paths['save_dir_base_path'])

    # RENAMED: Getter for the participants list path
    def get_participants_list_path(self) -> str:
        return self.config_paths['participants_list_file_path']