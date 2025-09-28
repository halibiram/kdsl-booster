import paramiko
import threading
import time
import logging

# Configure logging for better diagnostics
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s'
)

class EntwareSSHInterface:
    """
    A thread-safe, robust interface for managing a persistent SSH connection
    to an Entware environment, with automatic reconnection and command timeouts.
    """
    def __init__(self, host, username, password, ssh_port=22, keepalive_interval=30, connect_timeout=10):
        """
        Initializes the SSH interface.
        """
        self.host = host
        self.username = username
        self.password = password
        self.ssh_port = ssh_port
        self.keepalive_interval = keepalive_interval
        self.connect_timeout = connect_timeout

        self._ssh_client = None
        self._is_connected = False
        self._lock = threading.RLock()  # Re-entrant lock for safe nested calls
        self._stop_event = threading.Event()
        self._connection_thread = None

    def _create_ssh_client(self):
        """Creates and configures a new Paramiko SSH client instance."""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        return client

    def connect(self):
        """
        Establishes an SSH connection and starts the connection management thread.
        Raises an exception if the initial connection fails.
        """
        with self._lock:
            if self._is_connected:
                logging.info("Already connected.")
                return

            try:
                self._ssh_client = self._create_ssh_client()
                self._ssh_client.connect(
                    hostname=self.host,
                    port=self.ssh_port,
                    username=self.username,
                    password=self.password,
                    timeout=self.connect_timeout
                )
                self._is_connected = True
                logging.info("SSH connection established successfully.")

                self._stop_event.clear()
                self._connection_thread = threading.Thread(
                    target=self._manage_connection,
                    name="SSHConnectionManager",
                    daemon=True
                )
                self._connection_thread.start()
            except Exception as e:
                logging.error(f"Failed to establish initial SSH connection: {e}")
                self._is_connected = False
                if self._ssh_client:
                    self._ssh_client.close()
                self._ssh_client = None
                raise  # Re-raise the exception to the caller

    def disconnect(self):
        """
        Stops the connection manager and closes the SSH connection.
        """
        logging.info("Disconnecting...")
        with self._lock:
            if not self._connection_thread:
                logging.info("Not connected.")
                return

            self._stop_event.set()
            thread = self._connection_thread

        # Wait for the thread to finish outside the lock to avoid deadlocks
        if thread:
            thread.join()

        with self._lock:
            if self._ssh_client:
                self._ssh_client.close()
            self._ssh_client = None
            self._is_connected = False
            self._connection_thread = None
            logging.info("SSH connection closed.")

    def execute_command(self, command, timeout=15):
        """
        Executes a command on the remote device with a timeout.
        Returns (stdout, stderr) or (None, error_message) on failure.
        """
        with self._lock:
            if not self._is_connected or not self._ssh_client:
                logging.warning("Cannot execute command: SSH client is not connected.")
                return None, "Not connected"

            transport = self._ssh_client.get_transport()
            if not transport or not transport.is_active():
                logging.warning("Cannot execute command: SSH transport is not active.")
                return None, "Transport not active"

            try:
                _, stdout, stderr = self._ssh_client.exec_command(command, timeout=timeout)
                return stdout.read().decode(), stderr.read().decode()
            except Exception as e:
                logging.error(f"Failed to execute command '{command}': {e}")
                return None, str(e)

    def _manage_connection(self):
        """
        Core loop for the background thread. Monitors connection, sends keepalives,
        and triggers reconnection on failure.
        """
        while not self._stop_event.is_set():
            is_active = False
            with self._lock:
                if self._is_connected and self._ssh_client:
                    try:
                        is_active = self._ssh_client.get_transport().is_active()
                    except EOFError:
                        logging.warning("Connection check failed with EOFError.")
                        is_active = False

            if is_active:
                self.execute_command("echo 'keepalive'", timeout=10)
            else:
                logging.warning("Connection lost. Starting reconnection process.")
                self._handle_reconnection()

            # Wait for the specified interval or until a stop signal is received
            self._stop_event.wait(self.keepalive_interval)

    def _handle_reconnection(self):
        """
        Manages the reconnection logic with exponential backoff. This method
        is called by the management thread when a connection is lost.
        """
        reconnection_delay = 5
        max_reconnection_delay = 300

        while not self._stop_event.is_set():
            with self._lock:
                # Mark as disconnected during the attempt
                self._is_connected = False
                # Close the old client if it exists
                if self._ssh_client:
                    self._ssh_client.close()

                self._ssh_client = self._create_ssh_client()
                try:
                    logging.info(f"Attempting to reconnect to {self.host}...")
                    self._ssh_client.connect(
                        hostname=self.host, port=self.ssh_port,
                        username=self.username, password=self.password,
                        timeout=self.connect_timeout
                    )
                    self._is_connected = True
                    logging.info("Reconnection successful.")
                    return  # Exit the reconnection loop on success
                except Exception as e:
                    logging.error(f"Reconnection failed: {e}. Retrying in {reconnection_delay}s.")

            # Wait outside the lock to allow disconnect() to acquire it
            self._stop_event.wait(reconnection_delay)
            reconnection_delay = min(reconnection_delay * 2, max_reconnection_delay)