from typing import Dict, Optional, List
import re
from src.entware_ssh import EntwareSSHInterface
import logging

logger = logging.getLogger("dsl_bypass")

def discover_dsl_interfaces(ssh_interface: EntwareSSHInterface) -> Dict[str, dict]:
    """
    Advanced DSL interface discovery with chipset detection

    Returns:
        Dictionary with interface details including chipset info
    """
    logger.info("Discovering DSL interfaces with chipset detection...")
    interfaces = {}

    # Method 1: Check /sys/class/net
    stdout, _ = ssh_interface.execute_command("ls -la /sys/class/net 2>/dev/null")
    if stdout:
        for line in stdout.splitlines():
            iface_name = line.split()[-1] if line.split() else ""
            if any(keyword in iface_name.lower() for keyword in ["dsl", "ptm", "atm", "nas"]):
                interface_info = _probe_interface_details(ssh_interface, iface_name)
                if interface_info:
                    interfaces[iface_name] = interface_info

    # Method 2: Check /proc/net/dev
    stdout, _ = ssh_interface.execute_command("cat /proc/net/dev 2>/dev/null")
    if stdout:
        for line in stdout.splitlines():
            if any(keyword in line.lower() for keyword in ["dsl", "ptm", "atm"]):
                iface_name = line.split(':')[0].strip()
                if iface_name not in interfaces:
                    interface_info = _probe_interface_details(ssh_interface, iface_name)
                    if interface_info:
                        interfaces[iface_name] = interface_info

    # Method 3: Chipset-specific detection
    chipset = _detect_dsl_chipset(ssh_interface)
    if chipset:
        chipset_interfaces = _get_chipset_specific_interfaces(ssh_interface, chipset)
        interfaces.update(chipset_interfaces)

    if not interfaces:
        logger.warning("No DSL interfaces detected. Hardware may not be DSL-capable.")
        return {}

    logger.info(f"Discovered {len(interfaces)} DSL interface(s)")
    return interfaces


def _probe_interface_details(ssh_interface: EntwareSSHInterface,
                             iface_name: str) -> Optional[dict]:
    """
    Probe detailed information about a specific interface
    """
    details = {
        "name": iface_name,
        "path": f"/sys/class/net/{iface_name}",
        "type": "unknown",
        "driver": None,
        "operational": False
    }

    # Check if interface is operational
    stdout, _ = ssh_interface.execute_command(f"cat /sys/class/net/{iface_name}/operstate 2>/dev/null")
    if stdout:
        details["operational"] = "up" in stdout.lower()

    # Detect driver
    stdout, _ = ssh_interface.execute_command(f"readlink /sys/class/net/{iface_name}/device/driver 2>/dev/null")
    if stdout:
        details["driver"] = stdout.strip().split('/')[-1]

    # Determine interface type
    if "dsl" in iface_name.lower():
        details["type"] = "dsl"
    elif "ptm" in iface_name.lower():
        details["type"] = "ptm"  # Packet Transfer Mode (VDSL2)
    elif "atm" in iface_name.lower():
        details["type"] = "atm"  # ATM (ADSL)

    return details


def _detect_dsl_chipset(ssh_interface: EntwareSSHInterface) -> Optional[str]:
    """
    Detect DSL chipset (Broadcom, Lantiq, etc.)
    """
    # Check device tree
    stdout, _ = ssh_interface.execute_command("cat /proc/device-tree/compatible 2>/dev/null")
    if stdout:
        if "bcm63" in stdout.lower():
            match = re.search(r'bcm(\d+)', stdout.lower())
            if match:
                return f"BCM{match.group(1)}"
        elif "lantiq" in stdout.lower():
            return "Lantiq"

    # Check loaded kernel modules
    stdout, _ = ssh_interface.execute_command("lsmod | grep -i 'dsl\\|bcm\\|lantiq' 2>/dev/null")
    if stdout:
        if "bcm63138" in stdout.lower():
            return "BCM63138"
        elif "bcm6368" in stdout.lower():
            return "BCM6368"
        elif "lantiq" in stdout.lower() or "ltq" in stdout.lower():
            return "Lantiq"

    # Check /proc/driver
    stdout, _ = ssh_interface.execute_command("ls /proc/driver/ 2>/dev/null")
    if stdout:
        if "bcm" in stdout.lower():
            return "Broadcom"
        elif "lantiq" in stdout.lower() or "ltq_dsl" in stdout.lower():
            return "Lantiq"

    return None


def _get_chipset_specific_interfaces(ssh_interface: EntwareSSHInterface,
                                    chipset: str) -> Dict[str, dict]:
    """
    Get chipset-specific DSL interface paths
    """
    interfaces = {}

    if chipset.startswith("BCM"):
        # Broadcom chipset specific paths
        paths = [
            "/proc/bcm963xx/dsl",
            "/proc/driver/bcm_dsl",
            "/sys/devices/platform/bcm63xx-dsl"
        ]
        for path in paths:
            stdout, _ = ssh_interface.execute_command(f"test -e {path} && echo 'exists'")
            if stdout and "exists" in stdout:
                iface_name = path.split('/')[-1]
                interfaces[iface_name] = {
                    "name": iface_name,
                    "path": path,
                    "type": "chipset_specific",
                    "chipset": chipset,
                    "operational": True
                }

    elif chipset == "Lantiq":
        # Lantiq chipset specific paths
        paths = [
            "/proc/driver/ltq_dsl_cpe_api",
            "/sys/devices/platform/ltq_dsl"
        ]
        for path in paths:
            stdout, _ = ssh_interface.execute_command(f"test -e {path} && echo 'exists'")
            if stdout and "exists" in stdout:
                iface_name = path.split('/')[-1]
                interfaces[iface_name] = {
                    "name": iface_name,
                    "path": path,
                    "type": "chipset_specific",
                    "chipset": chipset,
                    "operational": True
                }

    return interfaces


def read_kernel_parameter(ssh_interface: EntwareSSHInterface,
                         param_path: str) -> Optional[str]:
    """
    Enhanced parameter reading with validation
    """
    logger.info(f"Reading kernel parameter from: {param_path}")

    # Validate path exists first
    stdout, _ = ssh_interface.execute_command(f"test -e {param_path} && echo 'exists'")
    if not stdout or "exists" not in stdout:
        logger.warning(f"Parameter path does not exist: {param_path}")
        return None

    # Check if path is readable
    stdout, _ = ssh_interface.execute_command(f"test -r {param_path} && echo 'readable'")
    if not stdout or "readable" not in stdout:
        logger.warning(f"Parameter path is not readable: {param_path}")
        return None

    # Read the parameter
    stdout, stderr = ssh_interface.execute_command(f"cat {param_path} 2>&1")

    if stderr and "permission denied" in stderr.lower():
        logger.error(f"Permission denied reading: {param_path}")
        return None

    if stderr and "no such file" in stderr.lower():
        logger.error(f"File not found: {param_path}")
        return None

    return stdout.strip() if stdout else None


def write_kernel_parameter(ssh_interface: EntwareSSHInterface,
                          param_path: str,
                          value: str,
                          validate: bool = True) -> bool:
    """
    Enhanced parameter writing with validation and backup
    """
    logger.info(f"Writing '{value}' to kernel parameter: {param_path}")

    # Backup original value
    original_value = None
    if validate:
        original_value = read_kernel_parameter(ssh_interface, param_path)
        if original_value is None:
            logger.warning(f"Cannot read original value from {param_path}")
            return False

    # Sanitize value
    sanitized_value = value.replace("'", "'\\''")

    # Check write permissions
    stdout, _ = ssh_interface.execute_command(f"test -w {param_path} && echo 'writable'")
    if not stdout or "writable" not in stdout:
        logger.error(f"Parameter path is not writable: {param_path}")
        logger.error("Try running with root privileges or check file permissions")
        return False

    # Write the parameter
    command = f"echo '{sanitized_value}' > {param_path} 2>&1"
    stdout, stderr = ssh_interface.execute_command(command)

    if stderr:
        logger.error(f"Error writing to kernel parameter: {stderr}")
        return False

    # Validate write if requested
    if validate:
        new_value = read_kernel_parameter(ssh_interface, param_path)
        if new_value != value:
            logger.error(f"Validation failed: expected '{value}', got '{new_value}'")
            # Attempt rollback
            if original_value:
                ssh_interface.execute_command(f"echo '{original_value}' > {param_path}")
            return False

    logger.info("Write operation completed successfully.")
    return True