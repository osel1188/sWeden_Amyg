import pytest
from unittest.mock import MagicMock, call

# Assuming pyvisa is installed, but we will mock it
import pyvisa

# Import the class and enums to be tested
from ti_system.waveform_generators.keysight_edu33212A import KeysightEDU33212A, OutputState, WaveformShape

# A constant for the resource ID used in tests
DUMMY_RESOURCE_ID = "TCPIP::DUMMY::INSTR"

@pytest.fixture
def mock_visa(mocker):
    """
    A pytest fixture to mock the entire pyvisa library.
    
    This fixture patches 'pyvisa.ResourceManager' where it is used in the driver,
    and yields both the mocked ResourceManager instance and the mocked 
    instrument resource it creates.
    """
    # Create a mock for the VISA resource (the instrument object).
    # The spec is removed to make the mock more flexible and avoid introspection issues.
    mock_instrument = MagicMock()
    mock_instrument.query.return_value = "KEYSIGHT,EDU33212A,12345,1.0.0" 
        
    # Create a mock for the ResourceManager
    mock_rm = MagicMock()
    mock_rm.open_resource.return_value = mock_instrument
    
    # MODIFICATION: Patch the ResourceManager class in the specific module where it is being used.
    # This is the crucial change to ensure the driver code uses our mock.
    mocker.patch('ti_system.waveform_generators.keysight_edu33212A.visa.ResourceManager', return_value=mock_rm)

    # Yield both mocks as a tuple so tests can make assertions on them
    yield mock_rm, mock_instrument


def test_connection_success(mock_visa):
    """
    Verifies that the connect() method performs the correct sequence of VISA calls.
    """
    mock_rm, mock_instrument = mock_visa # Unpack the mocks
    driver = KeysightEDU33212A(DUMMY_RESOURCE_ID, rst_delay=0)
    driver.connect()
    
    # Assert that the resource manager was asked to open the correct resource
    mock_rm.open_resource.assert_called_once_with(DUMMY_RESOURCE_ID)
    
    # Assert timeout was set on the instrument
    assert mock_instrument.timeout == 10000
    
    # Assert the sequence of initialization commands on the instrument
    mock_instrument.query.assert_called_once_with("*IDN?")
    mock_instrument.write.assert_has_calls([call('*RST'), call('*CLS')])


def test_connection_failure_raises_exception(mocker):
    """
    Verifies that a VisaIOError during connection is caught and re-raised as ConnectionError.
    """
    mock_rm = MagicMock()
    # Use a valid integer error code for VisaIOError.
    mock_rm.open_resource.side_effect = pyvisa.VisaIOError(-1073807343)
    # MODIFICATION: Ensure the patch target matches the one in the main fixture for consistency.
    mocker.patch('ti_system.waveform_generators.keysight_edu33212A.visa.ResourceManager', return_value=mock_rm)
    
    driver = KeysightEDU33212A(DUMMY_RESOURCE_ID)
    
    with pytest.raises(ConnectionError, match="VISA I/O Error connecting"):
        driver.connect()


def test_disconnect(mock_visa):
    """
    Verifies that the disconnect() method turns off outputs and closes the connection.
    """
    _mock_rm, mock_instrument = mock_visa # Unpack mocks, rm is not used here
    driver = KeysightEDU33212A(DUMMY_RESOURCE_ID)
    driver.connect() 
    
    mock_instrument.reset_mock()
    
    driver.disconnect()
    
    expected_write_calls = [
        call(':OUTPut1:STATe OFF'),
        call(':OUTPut2:STATe OFF')
    ]
    mock_instrument.write.assert_has_calls(expected_write_calls, any_order=False)
    mock_instrument.clear.assert_called_once()
    mock_instrument.close.assert_called_once()
    assert driver._instrument is None


def test_command_fails_when_not_connected():
    """
    Verifies that attempting to send a command before connecting raises a ConnectionError.
    """
    driver = KeysightEDU33212A(DUMMY_RESOURCE_ID)
    with pytest.raises(ConnectionError, match="Instrument not connected"):
        driver.set_frequency(1, 1000)


@pytest.mark.parametrize("channel, frequency, expected_scpi", [
    (1, 1000, ":SOURce1:FREQuency 1000.0000"),
    (2, 2500.5, ":SOURce2:FREQuency 2500.5000"),
    (1, 99.9, ":SOURce1:FREQuency 99.9000")
])
def test_set_frequency(mock_visa, channel, frequency, expected_scpi):
    """
    Uses parameterization to test the set_frequency method for both channels.
    """
    _mock_rm, mock_instrument = mock_visa
    driver = KeysightEDU33212A(DUMMY_RESOURCE_ID)
    driver.connect()
    
    mock_instrument.reset_mock() 
    
    driver.set_frequency(channel, frequency)
    mock_instrument.write.assert_called_with(expected_scpi)


@pytest.mark.parametrize("channel, shape, expected_scpi", [
    (1, WaveformShape.SINE, ":SOURce1:FUNCtion SIN"),
    (2, WaveformShape.SQUARE, ":SOURce2:FUNCtion SQU"),
    (1, WaveformShape.RAMP, ":SOURce1:FUNCtion RAMP"),
])
def test_set_waveform_shape(mock_visa, channel, shape, expected_scpi):
    """
    Tests the set_waveform_shape method using the WaveformShape enum.
    """
    _mock_rm, mock_instrument = mock_visa
    driver = KeysightEDU33212A(DUMMY_RESOURCE_ID)
    driver.connect()

    mock_instrument.reset_mock()

    driver.set_waveform_shape(channel, shape)
    mock_instrument.write.assert_called_with(expected_scpi)


def test_get_status_success(mock_visa):
    """
    Verifies that get_status correctly queries the instrument and formats the output.
    """
    _mock_rm, mock_instrument = mock_visa
    
    query_responses = {
        "*IDN?": "KEYSIGHT,EDU33212A,12345,1.0.0",
        ":OUTPut1:STATe?": "1",
        ":SOURce1:FUNCtion?": "SIN",
        ":SOURce1:FREQuency?": "1.000000E+03",
        ":SOURce1:VOLTage?": "2.500000E+00",
        ":SOURce1:VOLTage:OFFSet?": "1.000000E-01",
        ":OUTPut2:STATe?": "0",
        ":SOURce2:FUNCtion?": "SQU",
        ":SOURce2:FREQuency?": "5.000000E+03",
        ":SOURce2:VOLTage?": "1.000000E+00",
        ":SOURce2:VOLTage:OFFSet?": "0.000000E+00",
    }
    mock_instrument.query.side_effect = lambda cmd: query_responses[cmd]

    driver = KeysightEDU33212A(DUMMY_RESOURCE_ID)
    driver.connect()
    status = driver.get_status()

    assert status['connection'] == 'active'
    assert status['identity'] == "KEYSIGHT,EDU33212A,12345,1.0.0"
    
    assert status['channel_1']['output_state'] == "1"
    assert status['channel_1']['waveform'] == "SIN"
    assert status['channel_1']['frequency_hz'] == 1000.0
    assert status['channel_1']['amplitude_vpp'] == 2.5
    assert status['channel_1']['offset_v'] == 0.1
    
    assert status['channel_2']['frequency_hz'] == 5000.0