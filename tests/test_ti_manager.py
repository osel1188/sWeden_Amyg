# tests/test_ti_manager.py

import pytest
import json
from pathlib import Path

from temporal_interference.core.electrode import Electrode, ElectrodeGroup
from temporal_interference.core.system import TISystem
from temporal_interference.services.manager import TIManager
from temporal_interference.config import TIConfig


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
    test_dir = Path(__file__).parent
    config_file = test_dir / "ti_config.json"
    config_file.write_text(json.dumps(valid_config_data, indent=2))
    yield str(config_file)
    config_file.unlink()


def test_manager_initialization_success(valid_config_file: str):
    """
    Tests that the TIManager initializes correctly with a valid config file
    and populates its systems list.
    """
    manager = TIManager(config_path=valid_config_file)
    assert isinstance(manager.config_handler, TIConfig)
    # The new config has 2 systems (ti_A, ti_B)
    assert len(manager.ti_systems) == 2, "Should parse two systems from the config."
    assert isinstance(manager.ti_systems[0], TISystem)


def test_system_properties_are_correct(valid_config_file: str):
    """
    Tests that the parsed TISystem objects and their nested properties
    match the data in the configuration file.
    """
    manager = TIManager(config_path=valid_config_file)
    
    # Check the first system (ti_A from the config)
    system_one = manager.get_system(0)
    assert system_one.region == "amygdala's left side"
    
    # Check that electrode_pairs is a list of ElectrodeGroup objects
    assert isinstance(system_one.electrode_pairs, list)
    assert len(system_one.electrode_pairs) == 2
    assert isinstance(system_one.electrode_pairs[0], ElectrodeGroup)
    
    # Check the electrodes within the first group of the first system
    first_pair_electrodes = system_one.electrode_pairs[0].electrode_list
    assert len(first_pair_electrodes) == 2
    assert isinstance(first_pair_electrodes[0], Electrode)
    
    # Verify electrode data is correctly mapped for the first pair (A1)
    assert first_pair_electrodes[0].id == 1
    assert first_pair_electrodes[0].name == "electrode_1"
    assert first_pair_electrodes[0].region == "amygdala's left side"
    assert first_pair_electrodes[1].id == 2
    assert first_pair_electrodes[1].name == "electrode_2"

    # Verify electrode data for the second pair (A2) in the same system
    second_pair_electrodes = system_one.electrode_pairs[1].electrode_list
    assert second_pair_electrodes[0].id == 3
    assert second_pair_electrodes[0].name == "electrode_3"
    assert second_pair_electrodes[1].id == 4
    assert second_pair_electrodes[1].name == "electrode_4"


def test_initialization_raises_error_for_nonexistent_file():
    """
    Tests that TIManager raises an error if the config file path is invalid.
    """
    with pytest.raises(Exception): # Catches FileNotFoundError or a custom TIConfig error
        TIManager(config_path="non_existent_file.json")


def test_initialization_raises_error_for_malformed_json():
    """
    Tests that an error is raised for a syntactically incorrect JSON file.
    """
    test_dir = Path(__file__).parent
    malformed_file = test_dir / "malformed.json"
    # Note the extra trailing comma which makes the JSON invalid
    malformed_file.write_text('{ "hardware": { "electrodes": [{"id": 1},] } }')
    
    try:
        with pytest.raises(Exception): # Catches json.JSONDecodeError or custom TIConfig error
            TIManager(config_path=str(malformed_file))
    finally:
        if malformed_file.exists():
            malformed_file.unlink()


def test_initialization_raises_error_for_missing_keys(valid_config_data: dict):
    """
    Tests that an error is raised if the configuration is structurally invalid.
    """
    # Remove a required top-level key
    del valid_config_data["hardware"]
    
    test_dir = Path(__file__).parent
    invalid_config_file = test_dir / "invalid_config.json"
    invalid_config_file.write_text(json.dumps(valid_config_data))
    
    try:
        # This will likely raise a KeyError when parsing in _create_systems_from_config
        with pytest.raises(KeyError):
            TIManager(config_path=str(invalid_config_file))
    finally:
        if invalid_config_file.exists():
            invalid_config_file.unlink()


def test_get_system_method(valid_config_file: str):
    """
    Tests the get_system method for both valid and invalid indices.
    """
    manager = TIManager(config_path=valid_config_file)
    
    # Test valid index for system ti_A (index 0)
    system_a = manager.get_system(0)
    assert isinstance(system_a, TISystem)
    assert system_a.region == "amygdala's left side"
    # Check the ID of the first electrode in the second pair (channel A2)
    assert system_a.electrode_pairs[1].electrode_list[0].id == 3 
    
    # Test valid index for system ti_B (index 1)
    system_b = manager.get_system(1)
    assert isinstance(system_b, TISystem)
    assert system_b.region == "amygdala's right side"
    # Check the ID of the first electrode in the first pair (channel B1)
    assert system_b.electrode_pairs[0].electrode_list[0].id == 5

    # Test out-of-bounds index
    with pytest.raises(IndexError, match="TI system index out of range."):
        manager.get_system(2)

    with pytest.raises(IndexError, match="TI system index out of range."):
        manager.get_system(99)