import pytest
from unittest.mock import MagicMock
from src.keenetic_dsl_interface import KeeneticDSLInterface, KEENETIC_HARDWARE_MATRIX

@pytest.fixture
def mock_ssh_interface():
    """A fixture to create a mock EntwareSSHInterface."""
    return MagicMock()

@pytest.fixture
def dsl_interface(mock_ssh_interface):
    """A fixture to create a KeeneticDSLInterface with a mocked SSH interface."""
    return KeeneticDSLInterface(mock_ssh_interface)

def test_detect_hardware_success(dsl_interface, mock_ssh_interface):
    """
    Tests that detect_hardware correctly identifies a known model and loads its specs.
    """
    # Simulate the output of `cat /proc/device-tree/model` for a known device
    model_string = "Keenetic Giga (KN-1010)"
    mock_ssh_interface.execute_command.return_value = (model_string, "")

    detected_model = dsl_interface.detect_hardware()

    # Verify the command was executed
    mock_ssh_interface.execute_command.assert_called_once_with("cat /proc/device-tree/model")

    # Verify the correct model and specs were loaded
    assert detected_model == "KN-1010"
    assert dsl_interface.hardware_model == "KN-1010"
    assert dsl_interface.hardware_specs == KEENETIC_HARDWARE_MATRIX["KN-1010"]

def test_detect_hardware_unknown_model(dsl_interface, mock_ssh_interface):
    """
    Tests that detect_hardware returns None for an unknown model string.
    """
    model_string = "Some Unknown Router"
    mock_ssh_interface.execute_command.return_value = (model_string, "")

    detected_model = dsl_interface.detect_hardware()

    assert detected_model is None
    assert dsl_interface.hardware_model is None
    assert dsl_interface.hardware_specs is None

def test_detect_hardware_ssh_error(dsl_interface, mock_ssh_interface):
    """
    Tests that detect_hardware returns None when the SSH command fails.
    """
    mock_ssh_interface.execute_command.return_value = (None, "Permission denied")

    detected_model = dsl_interface.detect_hardware()

    assert detected_model is None

def test_get_dsl_register_address(dsl_interface):
    """
    Tests the calculation of a DSL register's absolute memory address.
    """
    # First, simulate that hardware has been detected
    dsl_interface.hardware_model = "KN-1010"
    dsl_interface.hardware_specs = KEENETIC_HARDWARE_MATRIX["KN-1010"]

    # Calculate a known register address
    snr_address = dsl_interface.get_dsl_register_address('snr_margin')

    # 0xBC000000 (base) + 0x1C08 (offset) = 0xBC001C08
    expected_address = 0xBC000000 + 0x1C08
    assert snr_address == expected_address

def test_get_dsl_register_address_for_unknown_register(dsl_interface):
    """
    Tests that get_dsl_register_address returns None for an undefined register.
    """
    dsl_interface.hardware_model = "KN-1010"
    dsl_interface.hardware_specs = KEENETIC_HARDWARE_MATRIX["KN-1010"]

    address = dsl_interface.get_dsl_register_address('non_existent_register')

    assert address is None

def test_get_dsl_register_address_before_detection(dsl_interface):
    """
    Tests that get_dsl_register_address returns None if hardware hasn't been detected.
    """
    address = dsl_interface.get_dsl_register_address('snr_margin')
    assert address is None

def test_read_dsl_register_success(dsl_interface, mock_ssh_interface):
    """
    Tests a successful read from a DSL register.
    """
    # Simulate hardware detection
    dsl_interface.hardware_model = "KN-2410"
    dsl_interface.hardware_specs = KEENETIC_HARDWARE_MATRIX["KN-2410"]

    # Expected address for profile_control on KN-2410 is 0xBE000000 + 0x2A04
    expected_address_hex = "0xbe002a04"

    # Simulate the output of a successful devmem2 read
    devmem_output = f"Value at address {expected_address_hex} (0x...): 0x11"
    mock_ssh_interface.execute_command.return_value = (devmem_output, "")

    value = dsl_interface.read_dsl_register('profile_control')

    # Verify the correct command was sent
    mock_ssh_interface.execute_command.assert_called_once_with(f"devmem2 {expected_address_hex}")

    # Verify the parsed value
    assert value == "0x11"

def test_write_dsl_register_success(dsl_interface, mock_ssh_interface):
    """
    Tests a successful write to a DSL register.
    """
    dsl_interface.hardware_model = "KN-1010"
    dsl_interface.hardware_specs = KEENETIC_HARDWARE_MATRIX["KN-1010"]

    expected_address_hex = "0xbc001c08" # snr_margin
    value_to_write = "0x100"

    # Simulate a successful write (no stderr output)
    mock_ssh_interface.execute_command.return_value = ("", "")

    result = dsl_interface.write_dsl_register('snr_margin', value_to_write)

    # Verify the correct command was sent
    expected_command = f"devmem2 {expected_address_hex} w {value_to_write}"
    mock_ssh_interface.execute_command.assert_called_once_with(expected_command)

    assert result is True

def test_write_dsl_register_ssh_error(dsl_interface, mock_ssh_interface):
    """
    Tests that a register write fails if the SSH command returns an error.
    """
    dsl_interface.hardware_model = "KN-1010"
    dsl_interface.hardware_specs = KEENETIC_HARDWARE_MATRIX["KN-1010"]

    # Simulate a failed write
    mock_ssh_interface.execute_command.return_value = (None, "devmem2: command not found")

    result = dsl_interface.write_dsl_register('snr_margin', '0x100')

    assert result is False