# ti_config.py

import json
import logging
import copy
from typing import Dict, List, Any

# Imports required for the new/modified methods
from .waveform_generators import AbstractWaveformGenerator, create_waveform_generator
from .electrode import Electrode, ElectrodePair
from .ti_channel import TIChannel
from .ti_system import TISystem

# --- Define the module-level logger ---
logger = logging.getLogger(__name__)

class TIConfig:
    """
    Manages the temporal interference (TI) stimulation configuration.
    Acts as a factory for TISystem objects based on the loaded config.
    
    MODIFIED: This class now instantiates all dependent objects,
    including TIChannels, and injects them into the TISystem.
    """
    def __init__(self, config_path: str = 'ti_config.json'):
        """
        Initializes the TIConfig class.

        Args:
            config_path (str): Path to the JSON configuration file.
        """
        self.config = self._load_config(config_path)
        if not self.config:
            # Error is already logged by _load_config
            raise ValueError("Failed to load or validate the configuration file.")
        
    def _validate_config(self, config: Dict) -> None:
        """
        Validates the structure, type, and presence of essential keys.

        MODIFICATION: Performs deep schema validation, checking types
        and structural integrity, not just key presence.

        Args:
            config (Dict): The loaded configuration dictionary.
        
        Raises:
            ValueError: If a required key, type, or structure is incorrect.
        """
        if not isinstance(config, dict):
            raise ValueError("Configuration root must be a JSON object (dict).")

        # --- Top Level Validation ---
        required_top_level: Dict[str, type] = {
            'hardware': dict,
            'waveform_generator_config': dict,
            'protocols': dict
        }
        for key, expected_type in required_top_level.items():
            if key not in config:
                raise ValueError(f"Configuration missing required top-level key: '{key}'")
            if not isinstance(config[key], expected_type):
                raise ValueError(f"Configuration key '{key}' must be of type {expected_type.__name__}, but got {type(config[key]).__name__}.")

        # --- Hardware Validation ---
        hardware_config = config['hardware']
        required_hardware: Dict[str, type] = {
            'waveform_generators': list,
            'electrodes': list,
            'ti_systems': dict
        }
        for key, expected_type in required_hardware.items():
            if key not in hardware_config:
                raise ValueError(f"Configuration missing required key in 'hardware': '{key}'")
            if not isinstance(hardware_config[key], expected_type):
                raise ValueError(f"Hardware key '{key}' must be of type {expected_type.__name__}, but got {type(config[key]).__name__}.")

        # Validate 'electrodes' content
        if not hardware_config['electrodes']:
            raise ValueError("'hardware.electrodes' list cannot be empty.")
        electrode_ids = set()
        for i, electrode in enumerate(hardware_config['electrodes']):
            if not isinstance(electrode, dict):
                raise ValueError(f"Item at index {i} in 'hardware.electrodes' is not a dict.")
            if 'id' not in electrode:
                raise ValueError(f"Item at index {i} in 'hardware.electrodes' is missing required key 'id'.")
            if electrode['id'] in electrode_ids:
                raise ValueError(f"Duplicate electrode ID '{electrode['id']}' found in 'hardware.electrodes'. IDs must be unique.")
            electrode_ids.add(electrode['id'])

        # Validate 'ti_systems' content
        if not hardware_config['ti_systems']:
            raise ValueError("'hardware.ti_systems' dict cannot be empty.")
        for system_key, system_data in hardware_config['ti_systems'].items():
            if not isinstance(system_data, dict):
                raise ValueError(f"Value for system '{system_key}' in 'hardware.ti_systems' is not a dict.")
            if 'channels' not in system_data:
                raise ValueError(f"System '{system_key}' is missing required key 'channels'.")
            if not isinstance(system_data['channels'], dict) or not system_data['channels']:
                    raise ValueError(f"'channels' for system '{system_key}' must be a non-empty dict.")
            
        # --- Waveform Generator Config Validation ---
        wg_config = config['waveform_generator_config']
        required_wg_config: Dict[str, type] = {
            'default': dict,
            'safety_limits': dict,
            'waveform_generator_presets_assignments': list
        }
        for key, expected_type in required_wg_config.items():
            if key not in wg_config:
                raise ValueError(f"Configuration missing required key in 'waveform_generator_config': '{key}'")
            if not isinstance(wg_config[key], expected_type):
                raise ValueError(f"Waveform config key '{key}' must be of type {expected_type.__name__}.")
        
        # --- Protocols Validation ---
        if not config['protocols']:
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
            with open(config_path, 'r') as f:
                config: Dict = json.load(f)
            logger.info(f"Configuration loaded successfully from {config_path}")
            
            # Content Management (Validation): Checks schema, types, and presence.
            self._validate_config(config)
            logger.info("Configuration validation successful.")
            
            return config
        
        except FileNotFoundError:
            logger.error(f"Configuration file not found: {config_path}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON configuration file {config_path}: {e}")
            return None
        except ValueError as e:
            # This catches failures from _validate_config
            logger.error(f"Configuration validation failed: {e}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred loading config {config_path}: {e}")
            return None

    def get_protocols(self) -> Dict[str, Any]:
        """
        Returns the 'protocols' dictionary from the loaded configuration.

        MODIFICATION: Returns a deep copy to prevent internal state mutation.

        Returns:
            Dict[str, Any]: A deep copy of the dictionary containing protocol definitions.
        """
        return copy.deepcopy(self.config.get('protocols', {}))

    def get_waveform_generator_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        Extracts all necessary configuration data for initializing
        waveform generators externally.
        
        MODIFICATION: Returns deep copies of preset configurations to
        prevent internal state mutation.

        Returns:
            Dict[str, Dict[str, Any]]: A dictionary where keys are
            generator IDs (e.g., 'wg_1') and values are dictionaries
            containing 'model', 'resource_id', and 'settings' (a deep copy
            of the preset config).
        """
        output_configs: Dict[str, Dict[str, Any]] = {}
        
        # Access internal config directly (read-only)
        hardware_config: Dict[str, Any] = self.config.get('hardware', {})
        wg_config_data: Dict[str, Any] = self.config.get('waveform_generator_config', {})
        
        preset_assignments: List[Dict] = wg_config_data.get('waveform_generator_presets_assignments', [])
        generator_config_list: List[Dict] = hardware_config.get('waveform_generators', [])

        # Iterate over all defined generators in hardware
        for generator_data in generator_config_list:
            try:
                generator_id: str = generator_data['id']
                model: str = generator_data['model']
                resource_name: str = generator_data['resource_name']
                
                # Find the assigned preset name for this generator
                preset_name: str | None = None
                # --- MODIFICATION: Store the entire assignment dict ---
                assignment_dict: Dict | None = None
                for assignment in preset_assignments:
                    if assignment.get('generator_id') == generator_id:
                        preset_name = assignment.get('preset')
                        assignment_dict = assignment # Store for overwrite access
                        break
                
                # Get the actual configuration dictionary from the preset name
                preset_config: Dict[str, Any] | None = None
                if preset_name:
                    #  Get a deep copy to prevent internal state mutation
                    preset_config = copy.deepcopy(wg_config_data.get(preset_name))
                    
                    if not preset_config:
                        logger.warning(f"Preset '{preset_name}' for generator '{generator_id}' not found. Settings will be None.")
                    
                    # --- MODIFICATION: Apply overwrites ---
                    elif assignment_dict:
                        overwrite_config = assignment_dict.get('overwrite')
                        if isinstance(overwrite_config, dict):
                            logger.info(f"Applying preset overwrites for generator '{generator_id}': {list(overwrite_config.keys())}")
                            # Merge overwrite dict, overwriting base preset keys
                            preset_config.update(overwrite_config)
                    # --- END MODIFICATION ---
                            
                else:
                    logger.warning(f"No preset assignment found for generator '{generator_id}'. Settings will be None.")

                # Assemble the complete configuration data required for initialization
                output_configs[generator_id] = {
                    'model': model,
                    'resource_id': resource_name,
                    'settings': preset_config  # This now contains merged settings
                }
            
            except KeyError as e:
                logger.error(f"Missing key {e} in 'waveform_generators' entry: {generator_data}. Skipping this generator config.")
                continue

        return output_configs

    def _initialize_waveform_generators(self) -> Dict[str, AbstractWaveformGenerator]:
        """
        Initializes all waveform generator hardware instances using the factory.

        This method retrieves the necessary configuration details, including
        safety limits and presets, and passes them to the generator factory.

        Returns:
            Dict[str, AbstractWaveformGenerator]: A dictionary mapping the
            generator ID (e.g., 'generator_A') to its initialized driver instance.
        
        Raises:
            ValueError: If the factory fails to create a generator instance
                        or if safety limits are missing.
        """
        initialized_generators: Dict[str, AbstractWaveformGenerator] = {}
        
        # 1. Get the configuration data (model, resource, settings) for all generators
        generator_configs = self.get_waveform_generator_configs()
        
        # 2. Get the global safety limits
        try:
            safety_limits = copy.deepcopy(self.config['waveform_generator_config']['safety_limits'])
        except KeyError:
            logger.error("Missing 'safety_limits' in 'waveform_generator_config'.")
            raise ValueError("Configuration missing 'safety_limits'.")

        # 3. Iterate and instantiate
        for gen_id, gen_config in generator_configs.items():
            try:
                # Prepare kwargs for the driver's constructor.
                # The factory will pass these through.
                kwargs = {
                    "settings": gen_config.get('settings'), # The preset dict
                    "safety_limits": safety_limits         # The global safety dict
                }
                
                logger.info(f"Initializing waveform generator: ID='{gen_id}', Model='{gen_config['model']}', Resource='{gen_config['resource_id']}'")
                
                # 4. Call the factory function from __init__.py
                wg_instance = create_waveform_generator(
                    model=gen_config['model'],
                    resource_id=gen_config['resource_id'],
                    **kwargs  # Pass settings and safety_limits to the driver
                )
                initialized_generators[gen_id] = wg_instance
            
            except Exception as e:
                logger.error(f"Failed to initialize waveform generator '{gen_id}' ({gen_config['model']}): {e}", exc_info=True)
                # Fail-fast: If hardware can't be initialized, the system cannot run.
                raise ValueError(f"Failed to initialize generator '{gen_id}': {e}")

        return initialized_generators
    
    def _create_electrode_pair(self, 
                               channel_config: Dict[str, Any], 
                               electrode_map: Dict[int, Dict], 
                               region: str, 
                               system_key: str, 
                               channel_key: str) -> ElectrodePair:
        """Helper to create an ElectrodePair from config data."""
        try:
            id_a: int = channel_config['electrode_id_A']
            id_b: int = channel_config['electrode_id_B']
        except KeyError as e:
            raise ValueError(f"Channel '{channel_key}' in system '{system_key}' is missing required key {e}.")

        if id_a not in electrode_map:
            raise ValueError(f"Invalid configuration: Electrode ID '{id_a}' (from system '{system_key}', channel '{channel_key}') not found in 'hardware.electrodes' list.")
        if id_b not in electrode_map:
            raise ValueError(f"Invalid configuration: Electrode ID '{id_b}' (from system '{system_key}', channel '{channel_key}') not found in 'hardware.electrodes' list.")
        
        electrode_data_a = electrode_map[id_a]
        electrode_data_b = electrode_map[id_b]

        electrode_a = Electrode(
            region=region,
            name=electrode_data_a.get('name', 'Unknown'),
            id=id_a
        )
        electrode_b = Electrode(
            region=region,
            name=electrode_data_b.get('name', 'Unknown'),
            id=id_b
        )

        return ElectrodePair(electrodes=(electrode_a, electrode_b))

    # --- REFINED METHOD ---
    def get_ti_systems(self) -> Dict[str, TISystem]:
        """
        Parses the loaded configuration and instantiates TISystem objects.

        MODIFICATION: This method now fully adopts the Factory pattern.
        It instantiates the waveform generators, electrode pairs, AND
        TIChannel objects, injecting them into the TISystem constructor.
        This requires a corresponding change to the TISystem.__init__ method.

        Returns:
            Dict[str, TISystem]: A dictionary of initialized TISystem objects,
                                  keyed by their system ID (e.g., 'ti_A').
        
        Raises:
            ValueError: If a referenced electrode_id is not found,
                        if a 'waveform_generator' is not specified for a channel,
                        if channels in the same system reference different generators,
                        if a referenced generator instance is not found,
                        or if 'ch1' or 'ch2' configs are missing.
        """
        systems_dict: Dict[str, TISystem] = {}
        
        # 1. Initialize all hardware instances defined in the config
        initialized_generators: Dict[str, AbstractWaveformGenerator] = self._initialize_waveform_generators()

        hardware_config: Dict[str, Any] = self.config.get('hardware', {})
        
        # 2. Create a lookup map for quick access to electrode data by ID.
        electrode_map: Dict[int, Dict] = {
            e['id']: e for e in hardware_config.get('electrodes', [])
        }
        
        ti_systems_config: Dict[str, Any] = hardware_config.get('ti_systems', {})

        # 3. Iterate over each defined TI system (e.g., ti_A, ti_B).
        for system_key, system_details in ti_systems_config.items():
            region: str = system_details.get('target', 'Unknown Region')
            channels_config: Dict[str, Any] = system_details.get('channels', {})
            
            # 4. Determine which single waveform generator this system uses
            #    (Validation logic is unchanged, 'ch1' presence is guaranteed by _validate_config)
            channels_dict: Dict[str, TIChannel] = {}
            generator_id_for_system: str | None = None
            for channel_key, channel_config in channels_config.items():
                wavegen_channel_id = channel_config.get('waveform_generator_channel')
                current_wg_id = channel_config.get('waveform_generator')
                
                if current_wg_id is None:
                    raise ValueError(f"Channel '{channel_key}' in system '{system_key}' is missing required key 'waveform_generator'.")
                
                # 5. Retrieve the initialized hardware instance for this channel
                try:
                    wg_instance = initialized_generators[current_wg_id]
                except KeyError:
                    raise ValueError(f"Configuration error: Waveform generator '{generator_id_for_system}' (used by system '{system_key}') is not defined in 'hardware.waveform_generators'.")
            
                #    is guaranteed by _validate_config)
                # 7. Create Electrode Pairs using the helper
                pair = self._create_electrode_pair(channel_config, electrode_map, region, system_key, channel_key)

                channels_dict[channel_key] = TIChannel(
                    channel_id=channel_key,
                    wavegen_channel_id=wavegen_channel_id,
                    electrode_pair=pair,
                    waveform_generator=wg_instance,
                    region_name=region
                )
            
            # 9. After creating all dependencies, create the TISystem.
            #    This assumes TISystem.__init__ has been modified to accept
            #    channel_1 and channel_2.
            try:
                ti_system = TISystem(
                    region=region,
                    channels=channels_dict
                )
                systems_dict[system_key] = ti_system
            except TypeError as e:
                logger.error(f"Failed to instantiate TISystem: {e}. Did you modify TISystem.__init__ to accept channel_1 and channel_2?")
                raise TypeError(f"TISystem constructor mismatch. See log. (Original error: {e})")
        
        return systems_dict