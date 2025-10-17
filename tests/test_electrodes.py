# test_electrodes.py

import pytest
from temporal_interference.electrode import Electrode, ElectrodeGroup

@pytest.fixture
def sample_electrodes():
    """Provides a list of sample Electrode objects for testing."""
    return [
        Electrode(region="PFC", name="Fp1", id=1),
        Electrode(region="PFC", name="Fp2", id=2),
        Electrode(region="Motor Cortex", name="C3", id=3),
    ]

# -----------------------------------------------------------------------------
# ## Success Scenarios
# -----------------------------------------------------------------------------

def test_electrode_group_creation_success_default_count(sample_electrodes):
    """
    Tests successful creation of an ElectrodeGroup using the default
    expected_count of 2.
    """
    # Arrange: Select the first two electrodes
    two_electrodes = sample_electrodes[:2]
    
    # Act: Create the group (should not raise an exception)
    group = ElectrodeGroup(electrode_list=two_electrodes, target_voltage=1.5)
    
    # Assert: Check that attributes are set correctly
    assert len(group.electrode_list) == 2
    assert group.target_voltage == 1.5

def test_electrode_group_creation_success_custom_count(sample_electrodes):
    """
    Tests successful creation of an ElectrodeGroup when providing a custom
    expected_count that matches the list length.
    """
    # Arrange: Use all three sample electrodes
    three_electrodes = sample_electrodes
    
    # Act: Create the group with a custom expected count
    group = ElectrodeGroup(
        electrode_list=three_electrodes,
        target_voltage=2.0,
        expected_count=3
    )
    
    # Assert
    assert len(group.electrode_list) == 3
    assert group.target_voltage == 2.0

# -----------------------------------------------------------------------------
# ## Failure Scenarios (Validation)
# -----------------------------------------------------------------------------

def test_electrode_group_creation_fails_wrong_default_count(sample_electrodes):
    """
    Tests that a ValueError is raised if the list length does not match
    the default expected_count of 2.
    """
    # Arrange: Use three electrodes where two are expected
    three_electrodes = sample_electrodes
    
    # Act & Assert: Use pytest.raises to catch the expected exception
    with pytest.raises(ValueError) as excinfo:
        ElectrodeGroup(electrode_list=three_electrodes)

    # Optionally, check the error message for correctness
    assert "must consist of exactly 2 Electrodes" in str(excinfo.value)
    assert "3 were provided" in str(excinfo.value)

def test_electrode_group_creation_fails_wrong_custom_count(sample_electrodes):
    """
    Tests that a ValueError is raised if the list length does not match
    a custom provided expected_count.
    """
    # Arrange: Use two electrodes where four are expected
    two_electrodes = sample_electrodes[:2]
    
    # Act & Assert
    with pytest.raises(ValueError) as excinfo:
        ElectrodeGroup(electrode_list=two_electrodes, expected_count=4)

    # Check the error message
    assert "must consist of exactly 4 Electrodes" in str(excinfo.value)
    assert "2 were provided" in str(excinfo.value)

def test_electrode_group_creation_fails_with_empty_list():
    """
    Tests that validation fails correctly for an empty list against the
    default expected_count.
    """
    with pytest.raises(ValueError) as excinfo:
        ElectrodeGroup(electrode_list=[])

    assert "0 were provided" in str(excinfo.value)

# -----------------------------------------------------------------------------
# ## Basic Electrode Test
# -----------------------------------------------------------------------------

def test_electrode_attributes():
    """
    A simple sanity check to ensure the Electrode dataclass works as expected.
    """
    # Arrange
    electrode = Electrode(region="Occipital", name="O1", id=10)
    
    # Assert
    assert electrode.region == "Occipital"
    assert electrode.name == "O1"
    assert electrode.id == 10