# tests/test_ti_manager.py

import pytest
import json
from pathlib import Path

from temporal_interference.electrode import Electrode, ElectrodeGroup
from temporal_interference.ti_system import TISystem
from temporal_interference.ti_manager import TIManager
from temporal_interference.ti_config import TIConfig


@pytest.fixture
def valid_config_data() -> dict:
    """Provides a valid dictionary for a test configuration based on ti_config_valid.json."""
    return {
        "hardware": {
            "waveform_generators": [
                {
                    "id": "generator_A",
                    "model": "keysight_edu33212A",
                    "resource_name": "USB0::0x2A8D::0x8D01::CN64050087::0::INSTR",
                    "comment": "Primary waveform generator."
                },
                {
                    "id": "generator_B",
                    "model": "keysight_edu33212A",
                    "resource_name": "USB0::0x2A8D::0x8D01::CN62490141::0::INSTR",
                    "comment": "Secondary waveform generator."
                }
            ],
            "electrodes": [
                { "id": 1, "name": "electrode_1" },
                { "id": 2, "name": "electrode_2" },
                { "id": 3, "name": "electrode_3" },
                { "id": 4, "name": "electrode_4" },
                { "id": 5, "name": "electrode_5" },
                { "id": 6, "name": "electrode_6" },
                { "id": 7, "name": "electrode_7" },
                { "id": 8, "name": "electrode_8" }
            ],
            "ti_systems": {
                "ti_A": {
                    "target": "amygdala's left side",
                    "channels": {
                        "A1": {
                            "waveform_generator": "generator_A",
                            "waveform_generator_channel": 1,
                            "electrode_id_A": 1,
                            "electrode_id_B": 2
                        },
                        "A2": {
                            "waveform_generator": "generator_A",
                            "waveform_generator_channel": 2,
                            "electrode_id_A": 3,
                            "electrode_id_B": 4
                        }
                    }
                },
                "ti_B": {
                    "target": "amygdala's right side",
                    "channels": {
                        "B1": {
                            "waveform_generator": "generator_B",
                            "waveform_generator_channel": 1,
                            "electrode_id_A": 5,
                            "electrode_id_B": 6
                        },
                        "B2": {
                            "waveform_generator": "generator_B",
                            "waveform_generator_channel": 2,
                            "electrode_id_A": 7,
                            "electrode_id_B": 8
                        }
                    }
                }
            }
        },
        "waveform_generator_config": {
            "default": {
                "function": "SIN",
                "load_impedance": "INFinity",
                "burst_num_cycles": "INFinity",
                "burst_state": True,
                "burst_mode": "TRIGgered",
                "burst_phase": 0
            },
            "safety_limits": {
                "max_voltage_v": 8.0
            },
            "waveform_generator_presets_assignments": [
                { "generator_id": "generator_A", "preset": "default" },
                { "generator_id": "generator_B", "preset": "default" }
            ]
        },
        "protocols": {
            "STIM": {
                "description": "Active stimulation protocol with a 130 Hz beat frequency.",
                "common_settings": { "target_voltage_V": 1.0, "ramp_duration_s": 60 },
                "ti_A": {
                    "channel_settings": [
                        { "channel": "A1", "frequency_hz": 7000 },
                        { "channel": "A2", "frequency_hz": 7130 }
                    ]
                },
                "ti_B": {
                    "channel_settings": [
                        { "channel": "B1", "frequency_hz": 9000 },
                        { "channel": "B2", "frequency_hz": 9130 }
                    ]
                }
            },
            "SHAM": {
                "description": "Sham protocol with no beat frequency and brief ramp.",
                "common_settings": { "target_voltage_V": 1.0, "ramp_duration_s": 60 },
                "ti_A": {
                    "channel_settings": [
                        { "channel": "A1", "frequency_hz": 7000 },
                        { "channel": "A2", "frequency_hz": 7000 }
                    ]
                },
                "ti_B": {
                    "channel_settings": [
                        { "channel": "B1", "frequency_hz": 9000 },
                        { "channel": "B2", "frequency_hz": 9000 }
                    ]
                }
            }
        }
    }


@pytest.fixture
def valid_config_file(valid_config_data: dict):
    """Creates a valid JSON config file in the test directory and cleans it up after the test."""
    # Get the directory of the current test file
    test_dir = Path(__file__).parent
    config_file = test_dir / "ti_config.json"
    config_file.write_text(json.dumps(valid_config_data, indent=2))
    
    # Provide the path to the test
    yield str(config_file)
    
    # Cleanup: remove the file after the test has finished
    config_file.unlink()


def test_manager_initialization_success(valid_config_file: str):
    """
    Tests that the TIManager initializes correctly with a valid config file
    and populates its channel list.
    """
    manager = TIManager(config_path=valid_config_file)
    assert isinstance(manager.config_handler, TIConfig)
    # The new config has 4 channels (A1, A2, B1, B2)
    assert len(manager.ti_channel_list) == 4, "Should parse four channels from the config."
    assert isinstance(manager.ti_channel_list[0], TISystem)


def test_channel_properties_are_correct(valid_config_file: str):
    """
    Tests that the parsed channel objects and their nested properties
    match the data in the configuration file.
    """
    manager = TIManager(config_path=valid_config_file)
    
    # Check the first channel (A1 from the config)
    channel_one = manager.get_channel(0)
    assert channel_one.region == "amygdala's left side"
    assert isinstance(channel_one.electrode_pairs, ElectrodeGroup)
    
    # Check the electrodes within the first channel's group
    electrodes = channel_one.electrode_pairs.electrode_list
    assert len(electrodes) == 2
    assert isinstance(electrodes[0], Electrode)
    
    # Verify electrode data is correctly mapped
    assert electrodes[0].id == 1
    assert electrodes[0].name == "electrode_1"
    assert electrodes[0].region == "amygdala's left side"
    assert electrodes[1].id == 2
    assert electrodes[1].name == "electrode_2"


def test_initialization_raises_error_for_nonexistent_file():
    """
    Tests that TIManager raises a ValueError if the config file path is invalid.
    (Internally, TIConfig returns None, triggering the ValueError in TIManager).
    """
    with pytest.raises(ValueError, match="Failed to load or validate the configuration file."):
        TIManager(config_path="non_existent_file.json")


def test_initialization_raises_error_for_malformed_json():
    """
    Tests that a ValueError is raised for a syntactically incorrect JSON file.
    """
    test_dir = Path(__file__).parent
    malformed_file = test_dir / "malformed.json"
    # Note the extra trailing comma which makes the JSON invalid
    malformed_file.write_text('{ "hardware": { "electrodes": [{"id": 1},] } }')
    
    try:
        with pytest.raises(ValueError, match="Failed to load or validate the configuration file."):
            TIManager(config_path=str(malformed_file))
    finally:
        # Ensure the temporary file is removed even if the test fails
        if malformed_file.exists():
            malformed_file.unlink()


def test_initialization_raises_error_for_missing_keys(valid_config_data: dict):
    """
    Tests that a ValueError is raised if the configuration is structurally
    invalid (e.g., missing a required top-level key like 'hardware').
    """
    # Remove a required top-level key
    del valid_config_data["hardware"]
    
    test_dir = Path(__file__).parent
    invalid_config_file = test_dir / "invalid_config.json"
    invalid_config_file.write_text(json.dumps(valid_config_data))
    
    try:
        with pytest.raises(ValueError, match="Failed to load or validate the configuration file."):
            TIManager(config_path=str(invalid_config_file))
    finally:
        # Ensure the temporary file is removed even if the test fails
        if invalid_config_file.exists():
            invalid_config_file.unlink()


def test_get_channel_method(valid_config_file: str):
    """
    Tests the get_channel method for both valid and invalid indices.
    """
    manager = TIManager(config_path=valid_config_file)
    
    # Test valid index for channel A2 (index 1)
    channel_a2 = manager.get_channel(1)
    assert isinstance(channel_a2, TISystem)
    assert channel_a2.electrode_pairs.electrode_list[0].id == 3 
    
    # Test valid index for channel B1 (index 2)
    channel_b1 = manager.get_channel(2)
    assert isinstance(channel_b1, TISystem)
    assert channel_b1.region == "amygdala's right side"
    assert channel_b1.electrode_pairs.electrode_list[0].id == 5

    # Test out-of-bounds index
    with pytest.raises(IndexError, match="Channel index out of range."):
        manager.get_channel(99)