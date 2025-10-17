# ti_manager.py

from typing import List, Dict, Any

from .ti_config import TIConfig
from .ti_system import TISystem
from .electrode import Electrode, ElectrodeGroup

class TIManager:
    """
    Manages all TI channels for the experiment by loading and interpreting
    a configuration file.
    """
    def __init__(self, config_path: str = 'ti_config.json'):
        """
        Initializes the TIManager.

        Args:
            config_path (str): The path to the JSON configuration file.
        """
        self.config_handler: TIConfig = TIConfig(config_path)
        self.ti_channel_list: List[TISystem] = []
        self._create_channels_from_config()
        
        print(f"TIManager initialized with {len(self.ti_channel_list)} channels from config.")

    def _create_channels_from_config(self) -> None:
        """
        Parses the loaded configuration and instantiates TISystem objects.
        """
        config_data: Dict[str, Any] = self.config_handler.config
        hardware_config: Dict[str, Any] = config_data.get('hardware', {})
        
        # Create a lookup map for quick access to electrode data by ID.
        electrode_map: Dict[int, Dict] = {
            e['id']: e for e in hardware_config.get('electrodes', [])
        }

        ti_systems: Dict[str, Any] = hardware_config.get('ti_systems', {})
        
        # Iterate over each defined TI system (e.g., ti_A, ti_B).
        for system_key, system_details in ti_systems.items():
            region: str = system_details.get('target', 'Unknown Region')
            
            # Iterate over each channel within the TI system (e.g., A1, A2).
            for channel_key, channel_config in system_details.get('channels', {}).items():
                
                # Get electrode IDs for the current pair.
                id_a: int = channel_config['electrode_id_A']
                id_b: int = channel_config['electrode_id_B']

                # Create Electrode instances.
                electrode_a = Electrode(
                    region=region,
                    name=electrode_map.get(id_a, {}).get('name', 'Unknown'),
                    id=id_a
                )
                electrode_b = Electrode(
                    region=region,
                    name=electrode_map.get(id_b, {}).get('name', 'Unknown'),
                    id=id_b
                )

                # Create the group for this pair.
                electrode_group = ElectrodeGroup(electrode_list=[electrode_a, electrode_b])
                
                # Create the TI channel.
                ti_channel = TISystem(region=region, electrode_pairs=electrode_group)
                
                # Add the fully configured channel to the manager.
                self.add_channel(ti_channel)
    
    def add_channel(self, channel: TISystem) -> None:
        """Adds a pre-configured TI channel to the manager."""
        self.ti_channel_list.append(channel)

    def get_channel(self, index: int) -> TISystem:
        """
        Retrieves a specific TI channel by its index.

        Args:
            index (int): The index of the channel to retrieve.

        Returns:
            TISystem: The requested TISystem object.
        
        Raises:
            IndexError: If the index is out of bounds.
        """
        if 0 <= index < len(self.ti_channel_list):
            return self.ti_channel_list[index]
        raise IndexError("Channel index out of range.")