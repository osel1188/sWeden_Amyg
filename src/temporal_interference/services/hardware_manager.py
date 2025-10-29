# hardware_manager.py

import logging
from typing import Set, Dict
from ..core.system import TISystem
from ..drivers.waveform_generator import AbstractWaveformGenerator

logger = logging.getLogger(__name__)

class HardwareManager:
    """
    Manages the lifecycle of all physical hardware (waveform generators)
    discovered from the TISystem objects.
    """
    def __init__(self, ti_systems: Dict[str, TISystem]):
        """
        Initializes the HardwareManager.

        Args:
            ti_systems (Dict[str, TISystem]): A reference to the dictionary
                of TI systems managed by the TIManager.
        """
        self.ti_systems = ti_systems

    def _discover_generators(self) -> Set[AbstractWaveformGenerator]:
        """
        Collects a set of all unique waveform generator hardware instances
        managed by the associated systems. This is called dynamically
        to ensure any newly-added systems are included.
        """
        all_generators: Set[AbstractWaveformGenerator] = set()
        for system in self.ti_systems.values():
            for channel in system.channels.values():
                all_generators.add(channel.generator)
        return all_generators

    def connect_all(self) -> None:
        """
        Connects to all hardware resources (waveform generators).
        """
        logger.info("Connecting to all hardware resources...")
        hardware = self._discover_generators()
        
        if not hardware:
            logger.warning("No hardware generators found to connect.")
            return

        for i, generator in enumerate(hardware):
            try:
                logger.info(f"Connecting to hardware '{generator.resource_id}' ({i+1}/{len(hardware)})...")
                generator.connect()
                logger.info(f"Successfully connected to '{generator.resource_id}'.")
            except Exception as e:
                logger.error(f"Failed to connect to hardware '{generator.resource_id}': {e}", exc_info=True)
                # Continue attempting to connect to other devices
        
        logger.info(f"Hardware connection attempt finished for {len(hardware)} devices.")

    def disconnect_all(self) -> None:
        """
        Disconnects from all hardware resources (waveform generators).
        """
        logger.info("Disconnecting from all hardware resources...")
        hardware = self._discover_generators()

        if not hardware:
            logger.warning("No hardware generators found to disconnect.")
            return

        for i, generator in enumerate(hardware):
            try:
                logger.info(f"Disconnecting from hardware '{generator.resource_id}' ({i+1}/{len(hardware)})...")
                generator.disconnect()
                logger.info(f"Successfully disconnected from '{generator.resource_id}'.")
            except Exception as e:
                logger.error(f"Failed to disconnect from hardware '{generator.resource_id}': {e}", exc_info=True)
        
        logger.info(f"Hardware disconnection finished for {len(hardware)} devices.")
        
    def enable_all(self) -> None:
        """
        Activates channels and enables output on all hardware generators.
        
        Raises:
            Exception: Re-raises any exceptions from the hardware layer.
        """
        hardware = self._discover_generators()
        logger.info(f"Preparing {len(hardware)} hardware generator(s)...")
        
        try:
            for gen in hardware:
                logger.debug(f"Activating channels on {gen.resource_id}")
                gen.activate_channels()
                
            for gen in hardware:
                logger.debug(f"Enabling device {gen.resource_id}")
                gen.enable_generation()
            
            logger.info("Hardware preparation complete.")
        except Exception as e:
            logger.critical(f"Failed to prepare hardware: {e}", exc_info=True)
            raise e # Re-raise for TIManager to handle

    def disable_all(self) -> None:
        """
        Disables output and deactivates channels on all hardware generators.
        
        Raises:
            Exception: Re-raises any exceptions from the hardware layer.
        """
        hardware = self._discover_generators()
        logger.info(f"Disabling {len(hardware)} hardware generator(s)...")
        
        try:
            for gen in hardware:
                logger.debug(f"Disabling device {gen.resource_id}")
                gen.disable_generation()

            for gen in hardware:
                logger.debug(f"Deactivating channels on {gen.resource_id}")
                gen.deactivate_channels()
                
            logger.info("Hardware disabling complete.")
        except Exception as e:
            logger.critical(f"Failed to disable hardware: {e}", exc_info=True)
            raise e # Re-raise for TIManager to handle