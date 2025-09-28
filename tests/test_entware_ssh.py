import pytest
import time
from src.entware_ssh import EntwareSSHInterface

@pytest.fixture
def ssh_interface_mocked(mocker):
    """
    A pytest fixture that provides a mocked EntwareSSHInterface instance.
    This fixture mocks the SSHClient, Thread, and Event classes for full control.
    """
    mocker.patch("paramiko.SSHClient")
    mock_thread_class = mocker.patch("threading.Thread")
    mock_event_class = mocker.patch("threading.Event")

    interface = EntwareSSHInterface(
        host="localhost",
        username="testuser",
        password="testpassword",
        keepalive_interval=1
    )

    # Replace the instance's thread and event objects with mocks
    interface._connection_thread = mock_thread_class.return_value
    interface._stop_event = mock_event_class.return_value

    # Mock the transport layer to simulate an active connection initially
    mock_transport = mocker.MagicMock()
    mock_transport.is_active.return_value = True
    interface.ssh_client.get_transport.return_value = mock_transport

    yield interface

    # Cleanly handle disconnect if thread was supposed to be running
    if interface.is_connected:
        interface.disconnect()

def test_connect_starts_thread(ssh_interface_mocked):
    """Tests that connect() starts the _manage_connection thread correctly."""
    ssh_interface_mocked.connect()

    ssh_interface_mocked.ssh_client.connect.assert_called_once()
    assert ssh_interface_mocked.is_connected
    ssh_interface_mocked._connection_thread.start.assert_called_once()

def test_disconnect_stops_thread(ssh_interface_mocked):
    """Tests that disconnect() stops the background thread and cleans up."""
    ssh_interface_mocked.is_connected = True # Simulate a connected state

    thread = ssh_interface_mocked._connection_thread

    ssh_interface_mocked.disconnect()

    assert not ssh_interface_mocked.is_connected
    ssh_interface_mocked._stop_event.set.assert_called_once()
    thread.join.assert_called_once()
    ssh_interface_mocked.ssh_client.close.assert_called_once()

def test_keepalive_mechanism(ssh_interface_mocked, mocker):
    """Tests that the keepalive mechanism sends commands periodically."""
    ssh_interface_mocked._stop_event.is_set.side_effect = [False, False, False, True]
    mock_execute = mocker.patch.object(ssh_interface_mocked, 'execute_command')

    ssh_interface_mocked.is_connected = True
    ssh_interface_mocked._manage_connection()

    assert mock_execute.call_count == 3
    mock_execute.assert_called_with("echo 'keepalive'")

def test_automatic_reconnection(ssh_interface_mocked, mocker):
    """Tests the automatic reconnection logic with exponential backoff."""
    # Simulate an initial connection drop
    ssh_interface_mocked.ssh_client.get_transport.return_value.is_active.return_value = False

    # Mock the SSHClient class to control the new instance created during reconnect
    new_mock_client = mocker.MagicMock()
    mocker.patch("paramiko.SSHClient", return_value=new_mock_client)

    # Reconnection fails once, then succeeds
    new_mock_client.connect.side_effect = [Exception("Connection failed"), None]

    # The new client needs its methods configured as well
    mock_stdout = mocker.MagicMock()
    mock_stdout.read.return_value = b"keepalive confirmation"
    new_mock_client.exec_command.return_value = (mocker.MagicMock(), mock_stdout, mocker.MagicMock())

    # Control the execution flow of the while loops
    ssh_interface_mocked._stop_event.is_set.side_effect = [
        False, # Outer loop starts
        False, # Inner (reconnect) loop, first attempt
        False, # Inner loop, second attempt
        True   # Outer loop terminates
    ]

    # Run the management loop
    ssh_interface_mocked.is_connected = True
    ssh_interface_mocked._manage_connection()

    # Assertions
    assert ssh_interface_mocked.is_connected
    assert not ssh_interface_mocked.is_reconnecting
    assert new_mock_client.connect.call_count == 2
    ssh_interface_mocked._stop_event.wait.assert_any_call(5) # Check first backoff