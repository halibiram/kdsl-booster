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
    This class is designed to be managed by a connection pool.
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
        self._is_reconnecting = False
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._connection_thread = None
        self.last_used = time.time()

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
                    name=f"SSHConnectionManager-{self.host}",
                    daemon=True
                )
                self._connection_thread.start()
            except Exception as e:
                logging.error(f"Failed to establish initial SSH connection: {e}")
                self._is_connected = False
                if self._ssh_client:
                    self._ssh_client.close()
                self._ssh_client = None
                raise

    def disconnect(self):
        """
        Stops the connection manager and closes the SSH connection.
        """
        logging.info(f"Disconnecting from {self.host}...")
        with self._lock:
            if not self._connection_thread:
                logging.info("Not connected.")
                return

            self._stop_event.set()
            thread = self._connection_thread

        if thread:
            thread.join(timeout=5.0) # Add a timeout to prevent hanging

        with self._lock:
            if self._ssh_client:
                self._ssh_client.close()
            self._ssh_client = None
            self._is_connected = False
            self._connection_thread = None
            logging.info("SSH connection closed.")

    def execute_command(self, command, timeout=15):
        """
        Executes a command on the remote device with a robust timeout.
        Returns (stdout, stderr) or (None, error_message) on failure.
        """
        with self._lock:
            self.last_used = time.time()
            if not self._is_connected or self._is_reconnecting:
                logging.warning("Cannot execute command: SSH client is not connected or reconnecting.")
                return None, "Not connected"

            try:
                stdin, stdout, stderr = self._ssh_client.exec_command(command, timeout=timeout)
                channel = stdout.channel

                start_time = time.time()
                while not channel.exit_status_ready():
                    if time.time() > start_time + timeout:
                        channel.close()
                        raise TimeoutError(f"Command '{command}' timed out after {timeout} seconds")
                    time.sleep(0.1)

                stdout_data = stdout.read().decode()
                stderr_data = stderr.read().decode()

                exit_status = channel.recv_exit_status()
                if exit_status != 0:
                    logging.warning(f"Command '{command}' exited with status {exit_status}. Stderr: {stderr_data.strip()}")

                return stdout_data, stderr_data

            except TimeoutError as e:
                logging.error(f"Timeout executing command '{command}': {e}")
                return None, str(e)
            except Exception as e:
                logging.error(f"Failed to execute command '{command}': {e}")
                # After a command failure, trigger a connection check
                with self._lock:
                    self._is_connected = False
                return None, str(e)

    def is_connected(self):
        """
        Checks if the SSH transport is active. Thread-safe.
        """
        with self._lock:
            if not self._is_connected or not self._ssh_client:
                return False
            try:
                transport = self._ssh_client.get_transport()
                return transport.is_active() if transport else False
            except EOFError:
                return False

    def _send_keepalive(self):
        """Separate keepalive logic"""
        try:
            with self._lock:
                if self._is_connected and self._ssh_client.get_transport():
                    # Use transport-level keepalive instead of command execution
                    transport = self._ssh_client.get_transport()
                    transport.send_ignore()
        except Exception as e:
            logging.warning(f"Keepalive failed: {e}")

    def _manage_connection(self):
        """
        Core loop for the background thread. Monitors connection, sends keepalives,
        and triggers reconnection on failure.
        """
        while not self._stop_event.is_set():
            should_reconnect = False
            with self._lock:
                is_active = False
                if self._is_connected and self._ssh_client and self._ssh_client.get_transport():
                    try:
                        is_active = self._ssh_client.get_transport().is_active()
                    except Exception:
                        is_active = False

                if not is_active and not self._is_reconnecting:
                    self._is_connected = False
                    self._is_reconnecting = True
                    should_reconnect = True

            if should_reconnect:
                self._attempt_reconnection()
            else:
                self._send_keepalive()
                self._stop_event.wait(self.keepalive_interval)

    def _attempt_reconnection(self):
        """Separate reconnection logic for clarity"""
        logging.info("Connection lost. Attempting to reconnect...")
        reconnection_delay = 5
        max_reconnection_delay = 300

        while not self._stop_event.is_set():
            try:
                # Close the old client and create a new one outside the main lock
                with self._lock:
                    if self._ssh_client:
                        self._ssh_client.close()
                    self._ssh_client = self._create_ssh_client()

                # Attempt to connect without holding the lock for the entire duration
                self._ssh_client.connect(
                    hostname=self.host,
                    port=self.ssh_port,
                    username=self.username,
                    password=self.password,
                    timeout=self.connect_timeout
                )

                # If connection is successful, update state under lock
                with self._lock:
                    self._is_connected = True
                    self._is_reconnecting = False
                logging.info("Reconnection successful.")
                break  # Exit the reconnection loop
            except Exception as e:
                logging.error(f"Reconnection failed: {e}. Retrying in {reconnection_delay}s...")
                self._stop_event.wait(reconnection_delay)
                reconnection_delay = min(reconnection_delay * 2, max_reconnection_delay)

class EntwareSSHConnectionPool:
    """
    A high-level manager for EntwareSSHInterface connections.
    It provides a simple, thread-safe way to get a single, persistent,
    and self-healing SSH connection.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(EntwareSSHConnectionPool, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, host, username, password, **kwargs):
        if self._initialized:
            return
        with self._lock:
            if self._initialized:
                return

            logging.info("Initializing SSH connection pool...")
            self.host = host
            self.username = username
            self.password = password
            self.ssh_kwargs = kwargs

            self._connection = None
            self._connection_lock = threading.Lock()
            self._initialized = True

    def get_connection(self):
        """
        Retrieves the singleton SSH connection, creating it if it doesn't exist.
        """
        with self._connection_lock:
            if self._connection is None or not self._connection.is_connected():
                logging.info("Connection not available or disconnected. Establishing new connection.")
                try:
                    self._connection = EntwareSSHInterface(
                        host=self.host,
                        username=self.username,
                        password=self.password,
                        **self.ssh_kwargs
                    )
                    self._connection.connect()
                except Exception as e:
                    logging.error(f"Failed to create connection in pool: {e}")
                    self._connection = None # Ensure connection is None on failure
                    raise

            return self._connection

    def close_all_connections(self):
        """
        Closes the managed SSH connection.
        """
        with self._connection_lock:
            if self._connection:
                self._connection.disconnect()
                self._connection = None
            logging.info("Connection pool has been shut down.")