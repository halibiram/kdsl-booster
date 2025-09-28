import paramiko
import threading
import time

class EntwareSSHInterface:
    """
    An interface for connecting to and managing an Entware environment over SSH,
    with built-in support for session persistence and automatic reconnection.
    """
    def __init__(self, host, username, password, ssh_port=22, entware_path="/opt", keepalive_interval=30):
        """
        Initializes the SSH interface.

        Args:
            host (str): The hostname or IP address of the target device.
            username (str): The SSH username.
            password (str): The SSH password.
            ssh_port (int): The SSH port.
            entware_path (str): The root path of the Entware installation.
            keepalive_interval (int): The interval in seconds for sending keepalive packets.
        """
        self.host = host
        self.username = username
        self.password = password
        self.ssh_port = ssh_port
        self.entware_root = entware_path
        self.dsl_tools_path = f"{entware_path}/bin"
        self.keepalive_interval = keepalive_interval

        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # State management attributes
        self.is_connected = False
        self.is_reconnecting = False
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._connection_thread = None

    def connect(self):
        """
        Establishes an SSH connection and starts the persistence manager thread.
        """
        with self._lock:
            if self.is_connected:
                print("Already connected.")
                return

            try:
                self.ssh_client.connect(
                    hostname=self.host,
                    port=self.ssh_port,
                    username=self.username,
                    password=self.password
                )
                self.is_connected = True
                print("SSH connection established successfully.")

                # Start the connection management thread
                self._stop_event.clear()
                self._connection_thread = threading.Thread(target=self._manage_connection)
                self._connection_thread.daemon = True
                self._connection_thread.start()

            except Exception as e:
                print(f"Failed to establish SSH connection: {e}")
                raise

    def disconnect(self):
        """
        Stops the persistence manager and closes the SSH connection.
        """
        with self._lock:
            if not self.is_connected:
                print("Not connected.")
                return

            # Signal the management thread to stop
            self._stop_event.set()
            if self._connection_thread:
                self._connection_thread.join()

            if self.ssh_client:
                self.ssh_client.close()

            self.is_connected = False
            print("SSH connection closed.")

    def execute_command(self, command):
        """
        Executes a command on the remote device.
        """
        with self._lock:
            if not self.is_connected:
                print("SSH client is not connected.")
                return None, None

            if not self.ssh_client.get_transport() or not self.ssh_client.get_transport().is_active():
                print("SSH transport is not active. Waiting for reconnect.")
                return None, None

            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            return stdout.read().decode(), stderr.read().decode()

    def _manage_connection(self):
        """
        The core loop for the background thread that manages the SSH connection.
        Handles keepalives and automatic reconnection.
        """
        while not self._stop_event.is_set():
            is_active = False
            if self.is_connected:
                try:
                    with self._lock:
                        if self.ssh_client.get_transport():
                            is_active = self.ssh_client.get_transport().is_active()
                except Exception:
                    is_active = False

            if not is_active:
                # Connection is down, attempt to reconnect.
                with self._lock:
                    self.is_connected = False
                    self.is_reconnecting = True

                print("Connection lost. Attempting to reconnect...")
                reconnection_delay = 5
                max_reconnection_delay = 300

                while not self._stop_event.is_set():
                    try:
                        with self._lock:
                            # Close old client and create a new one
                            self.ssh_client.close()
                            self.ssh_client = paramiko.SSHClient()
                            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                            self.ssh_client.connect(
                                hostname=self.host, port=self.ssh_port,
                                username=self.username, password=self.password, timeout=10
                            )
                            self.is_connected = True
                            self.is_reconnecting = False
                        print("Reconnection successful.")
                        break # Exit reconnection loop
                    except Exception as e:
                        print(f"Reconnection failed: {e}. Retrying in {reconnection_delay} seconds...")
                        self._stop_event.wait(reconnection_delay)
                        reconnection_delay = min(reconnection_delay * 2, max_reconnection_delay)

                if not self.is_connected:
                    # disconnect() was called during reconnection attempts
                    break

            # If we are here, we are connected (or just reconnected).
            # Send keepalive and wait.
            print("Sending keepalive...")
            self.execute_command("echo 'keepalive'")
            self._stop_event.wait(self.keepalive_interval)

    def detect_entware_environment(self):
        """
        Detects and verifies the Entware environment on the remote device.
        """
        print("Detecting Entware environment...")
        results = {
            "entware_root_found": False,
            "opkg_found": False,
            "installed_packages": None
        }

        # 1. Check for /opt mount point
        stdout, _ = self.execute_command(f"test -d {self.entware_root} && echo 'found'")
        if stdout and "found" in stdout:
            results["entware_root_found"] = True
            print(f"Entware root '{self.entware_root}' found.")

            # 2. Check for opkg tool
            stdout, _ = self.execute_command("which opkg")
            if stdout and self.entware_root in stdout:
                results["opkg_found"] = True
                print("opkg package manager found.")

                # 3. List installed packages (example)
                packages_stdout, _ = self.execute_command("opkg list-installed")
                if packages_stdout:
                    results["installed_packages"] = packages_stdout.splitlines()
                    print(f"Found {len(results['installed_packages'])} installed packages.")
            else:
                print("opkg package manager not found in Entware path.")
        else:
            print(f"Entware root '{self.entware_root}' not found.")

        return results