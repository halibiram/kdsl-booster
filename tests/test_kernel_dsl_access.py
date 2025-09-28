import pytest
from unittest.mock import MagicMock
from src.kernel_dsl_access import (
    discover_dsl_interfaces,
    read_kernel_parameter,
    write_kernel_parameter,
)

@pytest.fixture
def mock_ssh_interface():
    """Provides a mocked EntwareSSHInterface instance for testing."""
    return MagicMock()

def test_discover_dsl_interfaces_found(mock_ssh_interface):
    """
    Tests that DSL-related interfaces are correctly discovered when present.
    """
    # Simulate the output of 'ls /sys/class/net'
    mock_ssh_interface.execute_command.return_value = ("dsl0\neth0\nlo\nptm0\n", "")

    interfaces = discover_dsl_interfaces(mock_ssh_interface)

    mock_ssh_interface.execute_command.assert_called_once_with("ls /sys/class/net")
    assert "dsl0" in interfaces
    assert "ptm0" in interfaces
    assert "eth0" not in interfaces
    assert interfaces["dsl0"] == "/sys/class/net/dsl0"

def test_discover_dsl_interfaces_not_found(mock_ssh_interface):
    """
    Tests that hypothetical defaults are returned when no DSL interfaces are found.
    """
    mock_ssh_interface.execute_command.return_value = ("eth0\nlo\n", "")

    interfaces = discover_dsl_interfaces(mock_ssh_interface)

    assert "dsl0" in interfaces
    assert "ptm0" in interfaces
    assert "atm0" in interfaces
    assert interfaces["dsl0"] == "/sys/class/net/dsl0"

def test_read_kernel_parameter_success(mock_ssh_interface):
    """
    Tests successful reading of a kernel parameter.
    """
    param_path = "/sys/module/dsl/parameters/debug"
    mock_ssh_interface.execute_command.return_value = ("1\n", "")

    value = read_kernel_parameter(mock_ssh_interface, param_path)

    mock_ssh_interface.execute_command.assert_called_once_with(f"cat {param_path}")
    assert value == "1"

def test_read_kernel_parameter_failure(mock_ssh_interface):
    """
    Tests handling of a failure when reading a kernel parameter.
    """
    param_path = "/sys/module/dsl/parameters/nonexistent"
    mock_ssh_interface.execute_command.return_value = ("", "cat: read error: No such file or directory")

    value = read_kernel_parameter(mock_ssh_interface, param_path)

    assert value is None

def test_write_kernel_parameter_success(mock_ssh_interface):
    """
    Tests successful writing of a kernel parameter.
    """
    param_path = "/sys/module/dsl/parameters/debug"
    value_to_write = "0"
    mock_ssh_interface.execute_command.return_value = ("", "")

    success = write_kernel_parameter(mock_ssh_interface, param_path, value_to_write)

    expected_command = f"echo '{value_to_write}' > {param_path}"
    mock_ssh_interface.execute_command.assert_called_once_with(expected_command)
    assert success is True

def test_write_kernel_parameter_failure(mock_ssh_interface):
    """
    Tests handling of a failure when writing a kernel parameter.
    """
    param_path = "/sys/module/dsl/parameters/readonly"
    value_to_write = "1"
    mock_ssh_interface.execute_command.return_value = ("", "sh: write error: Permission denied")

    success = write_kernel_parameter(mock_ssh_interface, param_path, value_to_write)

    assert success is False

def test_write_kernel_parameter_sanitization(mock_ssh_interface):
    """
    Tests that values are properly sanitized to prevent command injection.
    """
    param_path = "/sys/module/dsl/parameters/debug"
    malicious_value = "1; rm -rf /"
    # The sanitization should wrap the value in single quotes, making it a literal string.
    sanitized_value = malicious_value.replace("'", "'\\''")
    expected_command = f"echo '{sanitized_value}' > {param_path}"
    mock_ssh_interface.execute_command.return_value = ("", "")

    write_kernel_parameter(mock_ssh_interface, param_path, malicious_value)

    mock_ssh_interface.execute_command.assert_called_once_with(expected_command)