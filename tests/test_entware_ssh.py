import pytest
from src.entware_ssh import EntwareSSHInterface

@pytest.fixture
def ssh_interface(mocker):
    """
    A pytest fixture that provides a mocked EntwareSSHInterface instance.
    The paramiko.SSHClient is mocked to prevent actual SSH connections.
    """
    mocker.patch("paramiko.SSHClient")
    interface = EntwareSSHInterface(
        host="localhost",
        username="testuser",
        password="testpassword"
    )
    return interface

def test_instantiation(ssh_interface):
    """
    Tests that the EntwareSSHInterface class is instantiated correctly.
    """
    assert ssh_interface is not None
    assert ssh_interface.host == "localhost"
    assert ssh_interface.username == "testuser"
    assert ssh_interface.password == "testpassword"
    assert ssh_interface.ssh_client.set_missing_host_key_policy.called

def test_connect(ssh_interface):
    """
    Tests the connect method, ensuring it calls the underlying SSH client's
    connect method with the correct parameters.
    """
    ssh_interface.connect()
    ssh_interface.ssh_client.connect.assert_called_once_with(
        hostname="localhost",
        port=22,
        username="testuser",
        password="testpassword"
    )

def test_disconnect(ssh_interface):
    """
    Tests the disconnect method to ensure it closes the SSH client connection.
    """
    # To test disconnect, we need to simulate a connected client
    ssh_interface.ssh_client.close.return_value = None
    ssh_interface.disconnect()
    ssh_interface.ssh_client.close.assert_called_once()

def test_execute_command(ssh_interface, mocker):
    """
    Tests the execute_command method, mocking the SSH client's exec_command
    to simulate command execution and verify the output.
    """
    # Simulate a connected transport
    mock_transport = mocker.MagicMock()
    mock_transport.is_active.return_value = True
    ssh_interface.ssh_client.get_transport.return_value = mock_transport

    # Mock stdin, stdout, and stderr
    mock_stdout = mocker.MagicMock()
    mock_stdout.read.return_value = b"command output"
    mock_stderr = mocker.MagicMock()
    mock_stderr.read.return_value = b"error output"

    ssh_interface.ssh_client.exec_command.return_value = (
        mocker.MagicMock(), mock_stdout, mock_stderr
    )

    stdout, stderr = ssh_interface.execute_command("ls -l")

    ssh_interface.ssh_client.exec_command.assert_called_once_with("ls -l")
    assert stdout == "command output"
    assert stderr == "error output"

def test_detect_entware_environment_success(ssh_interface, mocker):
    """
    Tests the detect_entware_environment method for a successful detection scenario.
    """
    # Mock the transport and command execution
    mock_transport = mocker.MagicMock()
    mock_transport.is_active.return_value = True
    ssh_interface.ssh_client.get_transport.return_value = mock_transport

    # Define the sequence of command outputs
    command_outputs = {
        "test -d /opt && echo 'found'": ("found\n", ""),
        "which opkg": ("/opt/bin/opkg\n", ""),
        "opkg list-installed": ("package1\npackage2\n", "")
    }

    def exec_command_side_effect(command):
        output = command_outputs.get(command, ("", ""))
        mock_stdout = mocker.MagicMock()
        mock_stdout.read.return_value = output[0].encode()
        mock_stderr = mocker.MagicMock()
        mock_stderr.read.return_value = output[1].encode()
        return (mocker.MagicMock(), mock_stdout, mock_stderr)

    ssh_interface.ssh_client.exec_command.side_effect = exec_command_side_effect

    results = ssh_interface.detect_entware_environment()

    assert results["entware_root_found"] is True
    assert results["opkg_found"] is True
    assert results["installed_packages"] == ["package1", "package2"]