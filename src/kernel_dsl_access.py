"""
This module provides functions for low-level interaction with DSL kernel interfaces.

It allows for the discovery of DSL-related network interfaces and provides
utilities to read from and write to kernel module parameters, which is essential
for the advanced spoofing techniques outlined in the DSL Bypass Ultra project.

All functions in this module are designed to be executed on a remote device
via the EntwareSSHInterface.
"""

from src.entware_ssh import EntwareSSHInterface

def discover_dsl_interfaces(ssh_interface: EntwareSSHInterface) -> dict:
    """
    Discovers DSL-related network interfaces on the remote system.

    It checks the /sys/class/net directory for interfaces that commonly
    relate to DSL connections, such as 'dsl', 'ptm', and 'atm'.

    Args:
        ssh_interface: An active EntwareSSHInterface instance.

    Returns:
        A dictionary where keys are the interface names (e.g., 'dsl0') and
        values are their full paths in the /sys/class/net directory.
    """
    print("Discovering DSL interfaces...")
    interfaces = {}

    # List all network interfaces
    stdout, stderr = ssh_interface.execute_command("ls /sys/class/net")

    if stderr or not stdout:
        print(f"Could not list network interfaces. Error: {stderr}")
        return interfaces

    all_interfaces = stdout.splitlines()

    # Filter for DSL-related interfaces
    dsl_keywords = ["dsl", "ptm", "atm"]
    for iface in all_interfaces:
        if any(keyword in iface for keyword in dsl_keywords):
            path = f"/sys/class/net/{iface}"
            interfaces[iface] = path
            print(f"Found DSL-related interface: {iface} at {path}")

    if not interfaces:
        print("No DSL-related interfaces found. Using hypothetical defaults.")
        # Fallback to defaults if none are discovered, as per README
        interfaces = {
            "dsl0": "/sys/class/net/dsl0",
            "ptm0": "/sys/class/net/ptm0",
            "atm0": "/sys/class/net/atm0"
        }

    return interfaces


def read_kernel_parameter(ssh_interface: EntwareSSHInterface, param_path: str) -> str | None:
    """
    Reads the value of a kernel parameter from a file in /sys or /proc.

    Args:
        ssh_interface: An active EntwareSSHInterface instance.
        param_path: The full path to the kernel parameter file.

    Returns:
        The value of the parameter as a string, or None if reading fails.
    """
    print(f"Reading kernel parameter from: {param_path}")
    stdout, stderr = ssh_interface.execute_command(f"cat {param_path}")

    if stderr:
        print(f"Error reading kernel parameter at {param_path}: {stderr}")
        return None

    return stdout.strip()


def write_kernel_parameter(ssh_interface: EntwareSSHInterface, param_path: str, value: str) -> bool:
    """
    Writes a value to a kernel parameter file in /sys or /proc.

    Note: This requires root privileges on the target device.

    Args:
        ssh_interface: An active EntwareSSHInterface instance.
        param_path: The full path to the kernel parameter file.
        value: The value to write to the parameter.

    Returns:
        True if the write operation was successful, False otherwise.
    """
    print(f"Writing '{value}' to kernel parameter: {param_path}")

    # Basic sanitization to prevent command injection
    sanitized_value = value.replace("'", "'\\''")
    command = f"echo '{sanitized_value}' > {param_path}"

    _, stderr = ssh_interface.execute_command(command)

    if stderr:
        print(f"Error writing to kernel parameter at {param_path}: {stderr}")
        return False

    print("Write operation completed.")
    return True