import pytest
import time
from unittest.mock import MagicMock, patch, call
from src.entware_ssh import EntwareSSHInterface
import paramiko
import threading

@pytest.fixture
def ssh_setup(mocker):
    """
    A robust fixture that mocks paramiko.SSHClient and provides a single,
    consistent mock client instance for testing the EntwareSSHInterface.
    This setup allows the background thread to run for realistic testing.
    """
    # Mock the entire paramiko.SSHClient class
    mock_ssh_client_class = mocker.patch('paramiko.SSHClient')

    # Create a single, reusable mock instance that the class will return
    mock_client_instance = MagicMock()

    # Configure the transport mock
    mock_transport = MagicMock()
    mock_transport.is_active.return_value = True
    mock_client_instance.get_transport.return_value = mock_transport

    # Configure exec_command to prevent errors in the keepalive thread
    mock_client_instance.exec_command.return_value = (MagicMock(), MagicMock(), MagicMock())

    # Set the class's return_value to our consistent instance
    mock_ssh_client_class.return_value = mock_client_instance

    interface = EntwareSSHInterface(
        host="mock_host",
        username="mock_user",
        password="mock_password",
        keepalive_interval=0.05 # Use a very short interval for fast testing
    )

    yield interface, mock_client_instance, mock_transport

    # Teardown: ensure the thread is stopped if it was started
    if interface._connection_thread and interface._connection_thread.is_alive():
        interface.disconnect()

def test_successful_connect_and_disconnect(ssh_setup):
    """
    Tests that the interface can connect, start its thread, and disconnect cleanly.
    """
    interface, mock_client, _ = ssh_setup

    interface.connect()

    assert interface._is_connected
    mock_client.connect.assert_called_once()
    assert interface._connection_thread.is_alive()

    interface.disconnect()

    assert not interface._is_connected
    mock_client.close.assert_called_once()
    assert interface._connection_thread is None

def test_keepalive_is_sent_periodically(ssh_setup):
    """
    Tests that the background thread sends keepalive commands.
    """
    interface, mock_client, _ = ssh_setup
    interface.connect()

    time.sleep(0.18) # Wait for ~3 keepalives

    interface.disconnect()

    assert mock_client.exec_command.call_count >= 3
    mock_client.exec_command.assert_any_call("echo 'keepalive'", timeout=10)

def test_automatic_reconnection_on_connection_drop(ssh_setup, mocker):
    """
    Tests that the interface attempts to reconnect when the transport becomes inactive.
    """
    interface, mock_client, mock_transport = ssh_setup

    # Spy on the connect method to count calls accurately
    connect_spy = mocker.spy(mock_client, 'connect')

    interface.connect()
    assert connect_spy.call_count == 1

    # Simulate connection drop
    mock_transport.is_active.return_value = False

    # Wait for the reconnection logic to trigger and call connect again
    time.sleep(0.2)

    assert connect_spy.call_count > 1

    interface.disconnect()

def test_reconnection_uses_exponential_backoff(mocker):
    """
    Tests the timing of reconnection attempts to verify exponential backoff.
    """
    interface = EntwareSSHInterface("h", "u", "p")

    mock_wait = mocker.patch.object(interface._stop_event, 'wait')
    mocker.patch.object(interface._stop_event, 'is_set').side_effect = [False, False, False, True]

    mock_client = MagicMock()
    mock_client.connect.side_effect = Exception("Connection failed")
    mocker.patch.object(interface, '_create_ssh_client', return_value=mock_client)

    interface._handle_reconnection()

    mock_wait.assert_has_calls([call(5), call(10), call(20)])

def test_execute_command_fails_when_not_connected(ssh_setup):
    """
    Tests that execute_command returns an error if called before connect().
    """
    interface, _, _ = ssh_setup
    assert not interface._is_connected

    stdout, stderr = interface.execute_command("ls")

    assert stdout is None
    assert stderr == "Not connected"