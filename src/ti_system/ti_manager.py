from typing import List
from .ti_channel import TIChannel

class TIManager:
    """Manages all TI channels for the experiment."""
    def __init__(self, num_channels: int = 4):
        self.ti_channel_list: List[TIChannel] = []
        # Placeholder for initializing channels based on hardware configuration.
        print(f"TIManager initialized for {num_channels} channels.")
    
    def add_channel(self, channel: TIChannel) -> None:
        """Adds a pre-configured TI channel to the manager."""
        self.ti_channel_list.append(channel)

    def get_channel(self, index: int) -> TIChannel:
        """Retrieves a specific TI channel by its index."""
        return self.ti_channel_list[index]
