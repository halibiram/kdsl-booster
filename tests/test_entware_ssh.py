import pytest
import time
from unittest.mock import MagicMock, patch, call
from src.entware_ssh import EntwareSSHInterface, EntwareSSHConnectionPool
import paramiko
import threading

# Fixture for EntwareSSHInterface tests
@pytest.fixture
def ssh_interface_setup(mocker):
    """
    Mocks paramiko.SSHClient for testing EntwareSSHInterface.
    """
    mock_ssh_client_class = mocker.patch('paramiko.SSHClient', autospec=True)
    mock_client_instance = mock_ssh_client_class.return_value

    mock_transport = MagicMock()
    mock_transport.is_active.return_value = True
    # Configure send_keepalive to avoid errors in the thread
    mock_transport.send_keepalive.return_value = None
    mock_client_instance.get_transport.return_value = mock_transport

    # Mock for exec_command channel
    mock_channel = MagicMock()
    mock_channel.recv_exit_status.return_value = 0
    mock_channel.exit_status_ready.return_value = True

    mock_stdout = MagicMock()
    mock_stdout.channel = mock_channel
    mock_stdout.read.return_value = b'output'

    mock_stderr = MagicMock()
    mock_stderr.read.return_value = b''

    mock_client_instance.exec_command.return_value = (MagicMock(), mock_stdout, mock_stderr)

    interface = EntwareSSHInterface(
        host="mock_host",
        username="mock_user",
        password="mock_password",
        keepalive_interval=0.05
    )

    yield interface, mock_client_instance, mock_transport

    if interface._connection_thread and interface._connection_thread.is_alive():
        interface.disconnect()

# Tests for EntwareSSHInterface
def test_interface_successful_connect_and_disconnect(ssh_interface_setup):
    interface, mock_client, _ = ssh_interface_setup
    interface.connect()
    assert interface.is_connected()
    mock_client.connect.assert_called_once()
    interface.disconnect()
    assert not interface.is_connected()
    mock_client.close.assert_called()

def test_interface_keepalive_is_sent(ssh_interface_setup):
    interface, _, mock_transport = ssh_interface_setup
    interface.connect()
    time.sleep(0.12)
    interface.disconnect()
    assert mock_transport.send_keepalive.call_count >= 2

def test_interface_automatic_reconnection(ssh_interface_setup):
    interface, mock_client, mock_transport = ssh_interface_setup
    interface.connect()
    assert mock_client.connect.call_count == 1

    mock_transport.is_active.return_value = False
    time.sleep(0.2)

    assert mock_client.connect.call_count > 1
    interface.disconnect()

def test_execute_command_timeout(ssh_interface_setup):
    interface, mock_client, _ = ssh_interface_setup

    mock_channel = MagicMock()
    mock_channel.exit_status_ready.return_value = False

    mock_stdout = MagicMock()
    mock_stdout.channel = mock_channel

    mock_client.exec_command.return_value = (MagicMock(), mock_stdout, MagicMock())

    interface.connect()
    stdout, stderr = interface.execute_command("sleep 5", timeout=0.1)

    assert stdout is None
    assert "timed out" in stderr.lower()
    interface.disconnect()

# Fixture for EntwareSSHConnectionPool tests
@pytest.fixture
def ssh_pool_setup(mocker):
    EntwareSSHConnectionPool._instance = None

    mock_interface_class = mocker.patch('src.entware_ssh.EntwareSSHInterface', autospec=True)

    # This will create new mock instances each time the class is called
    mock_interface_class.side_effect = lambda *args, **kwargs: MagicMock(spec=EntwareSSHInterface)

    pool = EntwareSSHConnectionPool(
        host="pool_host",
        username="pool_user",
        password="pool_password"
    )

    yield pool, mock_interface_class

    pool.close_all_connections()

# Tests for EntwareSSHConnectionPool
def test_pool_is_singleton():
    pool1 = EntwareSSHConnectionPool("host1", "user1", "pass1")
    pool2 = EntwareSSHConnectionPool("host2", "user2", "pass2")
    assert pool1 is pool2
    assert pool1.host == "host1"

def test_pool_get_connection_creates_and_returns_connection(ssh_pool_setup):
    pool, mock_interface_class = ssh_pool_setup

    conn = pool.get_connection()

    mock_interface_class.assert_called_once_with(
        host="pool_host", username="pool_user", password="pool_password"
    )
    conn.connect.assert_called_once()

def test_pool_get_connection_returns_existing_connection(ssh_pool_setup):
    pool, mock_interface_class = ssh_pool_setup

    conn1 = pool.get_connection()
    conn1.is_connected.return_value = True
    conn2 = pool.get_connection()

    assert conn1 is conn2
    mock_interface_class.assert_called_once()
    conn1.connect.assert_called_once()

def test_pool_recreates_connection_if_disconnected(ssh_pool_setup):
    pool, mock_interface_class = ssh_pool_setup

    conn1 = pool.get_connection()
    assert mock_interface_class.call_count == 1
    conn1.is_connected.return_value = False

    conn2 = pool.get_connection()

    assert mock_interface_class.call_count == 2
    assert conn1 is not conn2
    conn2.connect.assert_called_once()

def test_pool_close_all_connections(ssh_pool_setup):
    pool, _ = ssh_pool_setup

    conn = pool.get_connection()
    pool.close_all_connections()

    conn.disconnect.assert_called_once()
    assert pool._connection is None