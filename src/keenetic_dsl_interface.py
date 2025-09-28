import logging
from abc import ABC, abstractmethod
from src.entware_ssh import EntwareSSHInterface

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DslHalBase(ABC):
    """
    Abstract Base Class for a DSL Hardware Abstraction Layer.
    Defines the standard interface for interacting with different DSL chipsets.
    """
    def __init__(self, ssh: EntwareSSHInterface):
        self.ssh = ssh
        self.driver_path = None

    @abstractmethod
    def discover_driver(self) -> bool:
        """
        Dynamically discovers the path to the DSL driver files or commands.
        Returns:
            True if the driver/command was found, False otherwise.
        """
        pass

    @abstractmethod
    def get_snr_margin(self) -> float | None:
        """
        Reads the current SNR margin from the DSL modem.
        Returns:
            The SNR margin in dB, or None on failure.
        """
        pass

    @abstractmethod
    def set_snr_margin(self, snr_margin: int) -> bool:
        """
        Sets a new target SNR margin on the DSL modem.
        Args:
            snr_margin: The target SNR margin value.
        Returns:
            True on success, False on failure.
        """
        pass

class BroadcomDslHal(DslHalBase):
    """
    HAL for Broadcom DSL chipsets (e.g., BCM63xx series).
    These chipsets are often controlled via proprietary command-line tools.
    """
    def discover_driver(self) -> bool:
        logging.info("Searching for Broadcom DSL control utility (e.g., xdslctl)...")

        possible_tools = ["xdslctl", "bcm_xdslctl", "adslctl"]

        for tool in possible_tools:
            command = f"command -v {tool}"
            stdout, _ = self.ssh.execute_command(command, timeout=5)

            if stdout and stdout.strip():
                self.driver_path = stdout.strip()
                logging.info(f"Found Broadcom DSL control utility at: {self.driver_path}")
                return True

        logging.error("Could not find a valid Broadcom DSL control utility.")
        self.driver_path = None
        return False

    def get_snr_margin(self) -> float | None:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return None

        command = f"{self.driver_path} info --show"
        stdout, stderr = self.ssh.execute_command(command)

        if stderr or not stdout:
            logging.error(f"Failed to get Broadcom DSL info: {stderr}")
            return None

        for line in stdout.splitlines():
            if "SNR Margin" in line or "snr_margin" in line:
                try:
                    return float(line.split(':')[1].strip().split(' ')[0])
                except (IndexError, ValueError) as e:
                    logging.warning(f"Could not parse SNR margin from line: '{line}'. Error: {e}")
                    continue
        return None

    def set_snr_margin(self, snr_margin: int) -> bool:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return False

        command = f"{self.driver_path} configure --snr {snr_margin}"
        _, stderr = self.ssh.execute_command(command)

        if stderr:
            logging.error(f"Failed to set Broadcom SNR margin: {stderr}")
            return False
        return True

class LantiqDslHal(DslHalBase):
    """
    HAL for Lantiq (now Intel) DSL chipsets (e.g., VRX208/VRX288).
    These chipsets often expose their state via the /sys filesystem.
    """
    def discover_driver(self) -> bool:
        logging.info("Searching for Lantiq DSL driver path in /sys/class/dsl...")

        command = "find /sys/class/dsl/dsl* -name 'adsl_version' -print -quit | sed 's|/adsl_version$||'"
        stdout, stderr = self.ssh.execute_command(command, timeout=5)

        if stderr or not stdout.strip():
            logging.error(f"Could not find a valid Lantiq DSL driver path. Error: {stderr or 'No output'}")
            self.driver_path = None
            return False

        self.driver_path = stdout.strip()
        logging.info(f"Found Lantiq DSL driver at: {self.driver_path}")
        return True

    def get_snr_margin(self) -> float | None:
        if not self.driver_path:
            return None

        command = f"cat {self.driver_path}/snr_margin_downstream"
        stdout, stderr = self.ssh.execute_command(command)

        if stderr or not stdout:
            logging.error(f"Failed to read Lantiq SNR margin: {stderr}")
            return None

        try:
            # Value is often stored in 1/10th of a dB
            return float(stdout.strip()) / 10.0
        except ValueError:
            return None

    def set_snr_margin(self, snr_margin: int) -> bool:
        if not self.driver_path:
            return False

        command = f"echo {snr_margin} > {self.driver_path}/snr_margin_target"
        _, stderr = self.ssh.execute_command(command)

        if stderr:
            logging.error(f"Failed to set Lantiq SNR margin: {stderr}")
            return False
        return True

# Maps Keenetic models to their corresponding DSL HAL implementation.
CHIPSET_FAMILY_MAP = {
    'KN-1010': BroadcomDslHal,  # Keenetic Giga uses a Broadcom DSL chip
    'KN-2410': LantiqDslHal,    # Keenetic Viva uses a Lantiq DSL chip
}

class KeeneticDSLInterface:
    """
    Hardware-aware factory for creating DSL HAL instances for Keenetic routers.
    It detects the router model and instantiates the correct HAL.
    """
    def __init__(self, ssh_interface: EntwareSSHInterface):
        self.ssh = ssh_interface
        self._hal_instance = None
        self._hal_class = None

    def _detect_hal_class(self) -> type[DslHalBase] | None:
        if self._hal_class:
            return self._hal_class

        logging.info("Detecting Keenetic hardware model to determine HAL class...")
        command = "cat /proc/device-tree/model"
        stdout, stderr = self.ssh.execute_command(command)

        if stderr or not stdout:
            logging.error(f"Failed to detect hardware model: {stderr or 'No output'}")
            return None

        model_string = stdout.strip()
        logging.info(f"Detected model string: '{model_string}'")

        for model_key, hal_class in CHIPSET_FAMILY_MAP.items():
            if model_key in model_string:
                logging.info(f"Matched model {model_key}, using HAL: {hal_class.__name__}")
                self._hal_class = hal_class
                return self._hal_class

        logging.error(f"No HAL class found for model '{model_string}'")
        return None

    def get_hal(self) -> DslHalBase | None:
        if self._hal_instance:
            return self._hal_instance

        hal_class = self._detect_hal_class()
        if not hal_class:
            return None

        hal_instance = hal_class(self.ssh)

        if hal_instance.discover_driver():
            self._hal_instance = hal_instance
            return self._hal_instance
        else:
            logging.error(f"Failed to discover driver for HAL {hal_class.__name__}")
            return None