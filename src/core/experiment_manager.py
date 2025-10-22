import json
from pathlib import Path
from ..ti_system import create_waveform_generator
from ..ti_system.ti_manager import TIManager
from ..ti_system.waveform_generators.waveform_generator import AbstractWaveformGenerator
from ..participant.participant_manager import ParticipantManager
from ..utils.logging_manager import LogFileManager
from ..utils.interface import BaseInterface

class ExperimentManager:
    """The central orchestrator for the entire experimental flow."""
    def __init__(self, interface: BaseInterface, config_path: Path):
        # Load configuration from JSON file
        with open(config_path, 'r') as f:
            config = json.load(f)

        log_path = Path(config.get("log_file_path", "experiment.log"))
        data_path = Path(config.get("participant_data_path", "data/participants"))
        
        self.ti_manager = TIManager(num_channels=config.get("num_ti_channels", 4))
        self.participant_manager = ParticipantManager(data_path=data_path)
        self.log_file_manager = LogFileManager(log_file=log_path)
        self.interface = interface
        
        # Use the factory to create the specified waveform generator
        self.waveform_generator: AbstractWaveformGenerator = create_waveform_generator(config['waveform_generator'])
        
        self.log_file_manager.log("ExperimentManager initialized.", "info")
        self.log_file_manager.log(f"Using waveform generator: {config['waveform_generator']['class']}", "info")

    def run(self) -> None:
        """Starts and executes the main experiment loop."""
        self.log_file_manager.log("Experiment run started.", "info")
        self.interface.display_message("Experiment is now running.")
        
        # Connect to hardware
        self.waveform_generator.connect()
        
        # --- Main experiment logic uses the abstract interface ---
        # self.waveform_generator.apply_waveform(...)
        
        self.interface.display_message("Experiment finished.")
        self.log_file_manager.log("Experiment run finished.", "info")

        # Disconnect from hardware
        self.waveform_generator.disconnect()