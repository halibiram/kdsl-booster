import pytest
from unittest.mock import MagicMock, call
from src.keenetic_dsl_interface import (
    KeeneticDSLInterface,
    BroadcomDslHal,
    LantiqDslHal,
    CHIPSET_FAMILY_MAP
)

# Mock SSH Interface Fixture
@pytest.fixture
def mock_ssh():
    """Provides a mock of the EntwareSSHInterface."""
    return MagicMock()

# KeeneticDSLInterface (Factory) Tests
@pytest.mark.parametrize("model_key, model_string, expected_hal_class", [
    ("KN-1010", "Keenetic Giga (KN-1010)", BroadcomDslHal),
    ("KN-2410", "Keenetic Viva (KN-2410)", LantiqDslHal),
])
def test_factory_detects_correct_hal(mock_ssh, model_key, model_string, expected_hal_class):
    """
    Tests that the factory instantiates the correct HAL based on the detected model.
    """
    # Simulate model detection and successful driver discovery
    mock_ssh.execute_command.side_effect = [
        (model_string, ""),  # First call for model detection
        ("/path/to/driver", "")  # Second call for driver discovery
    ]

    factory = KeeneticDSLInterface(mock_ssh)
    hal_instance = factory.get_hal()

    assert isinstance(hal_instance, expected_hal_class)
    assert factory._hal_class == expected_hal_class

    # Check that model detection was called
    mock_ssh.execute_command.assert_any_call("cat /proc/device-tree/model")

def test_factory_returns_none_for_unknown_model(mock_ssh):
    """
    Tests that the factory returns None if the router model is not in the map.
    """
    mock_ssh.execute_command.return_value = ("Unknown Model XYZ", "")

    factory = KeeneticDSLInterface(mock_ssh)
    hal_instance = factory.get_hal()

    assert hal_instance is None

def test_factory_returns_none_if_driver_discovery_fails(mock_ssh):
    """
    Tests that the factory returns None if the HAL fails to find its driver.
    """
    # Simulate model detection, but make all driver discovery attempts fail
    mock_ssh.execute_command.side_effect = [
        ("Keenetic Giga (KN-1010)", ""),  # 1. Model detection
        ("", "not found"),                # 2. command -v xdslctl
        ("", "not found"),                # 3. command -v bcm_xdslctl
        ("", "not found"),                # 4. command -v adslctl
    ]

    factory = KeeneticDSLInterface(mock_ssh)
    hal_instance = factory.get_hal()

    assert hal_instance is None

# BroadcomDslHal Tests
def test_broadcom_hal_discover_driver_success(mock_ssh):
    """Tests successful discovery of a Broadcom control utility."""
    mock_ssh.execute_command.side_effect = [
        ("", ""),  # 'command -v xdslctl' fails
        ("/usr/sbin/bcm_xdslctl", ""),  # 'command -v bcm_xdslctl' succeeds
    ]

    hal = BroadcomDslHal(mock_ssh)
    assert hal.discover_driver() is True
    assert hal.driver_path == "/usr/sbin/bcm_xdslctl"

    expected_calls = [
        call("command -v xdslctl", timeout=5),
        call("command -v bcm_xdslctl", timeout=5)
    ]
    mock_ssh.execute_command.assert_has_calls(expected_calls)

def test_broadcom_hal_get_snr_margin(mock_ssh):
    """Tests parsing SNR margin from Broadcom utility output."""
    hal = BroadcomDslHal(mock_ssh)
    hal.driver_path = "/usr/sbin/xdslctl" # Assume driver is found

    mock_output = """
    Status: Showtime
    SNR Margin (dB): 12.3 10.1
    """
    mock_ssh.execute_command.return_value = (mock_output, "")

    snr = hal.get_snr_margin()

    mock_ssh.execute_command.assert_called_with("/usr/sbin/xdslctl info --show")
    assert snr == 12.3

# LantiqDslHal Tests
def test_lantiq_hal_discover_driver_success(mock_ssh):
    """Tests successful discovery of a Lantiq driver path."""
    mock_ssh.execute_command.return_value = ("/sys/class/dsl/dsl0", "")

    hal = LantiqDslHal(mock_ssh)

    assert hal.discover_driver() is True
    assert hal.driver_path == "/sys/class/dsl/dsl0"

    expected_command = "find /sys/class/dsl/dsl* -name 'adsl_version' -print -quit | sed 's|/adsl_version$||'"
    mock_ssh.execute_command.assert_called_once_with(expected_command, timeout=5)

def test_lantiq_hal_get_snr_margin(mock_ssh):
    """Tests reading and parsing SNR margin from a Lantiq sysfs file."""
    hal = LantiqDslHal(mock_ssh)
    hal.driver_path = "/sys/class/dsl/dsl0" # Assume driver is found

    # Simulate the content of the snr_margin_downstream file (value is in 1/10 dB)
    mock_ssh.execute_command.return_value = ("98", "")

    snr = hal.get_snr_margin()

    mock_ssh.execute_command.assert_called_with("cat /sys/class/dsl/dsl0/snr_margin_downstream")
    assert snr == 9.8

def test_lantiq_hal_set_snr_margin(mock_ssh):
    """Tests writing a new SNR margin target to a Lantiq sysfs file."""
    hal = LantiqDslHal(mock_ssh)
    hal.driver_path = "/sys/class/dsl/dsl0"
    mock_ssh.execute_command.return_value = ("", "") # Simulate success

    result = hal.set_snr_margin(50) # Set target to 50%

    expected_command = "echo 50 > /sys/class/dsl/dsl0/snr_margin_target"
    mock_ssh.execute_command.assert_called_once_with(expected_command)
    assert result is True