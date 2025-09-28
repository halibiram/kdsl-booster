import logging
from src.entware_ssh import EntwareSSHInterface

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Hardware Abstraction Layer (HAL) data
KEENETIC_HARDWARE_MATRIX = {
    'KN-1010': {  # Keenetic Giga
        'chipset': 'MT7621A',
        'dsl_chip': 'BCM63138',
        'register_base': 0xBC000000,
        'dsl_registers': {
            'profile_control': 0x1C04,
            'snr_margin': 0x1C08,
            'attenuation': 0x1C0C
        }
    },
    'KN-2410': {  # Keenetic Viva
        'chipset': 'MT7628A',
        'dsl_chip': 'Lantiq_VRX208',
        'register_base': 0xBE000000,
        'dsl_registers': {
            'profile_control': 0x2A04,
            'snr_margin': 0x2A08
        }
    }
}

class KeeneticDSLInterface:
    """
    A hardware-aware interface for low-level DSL manipulation on Keenetic routers.
    This class detects the hardware model and uses a Hardware Abstraction Layer (HAL)
    to interact with the correct DSL chipset drivers and registers.
    """
    def __init__(self, ssh_interface: EntwareSSHInterface):
        """
        Initializes the DSL interface.

        Args:
            ssh_interface: An active and authenticated EntwareSSHInterface instance.
        """
        self.ssh = ssh_interface
        self.hardware_model = None
        self.hardware_specs = None

    def detect_hardware(self) -> str | None:
        """
        Detects the Keenetic hardware model by reading system information.
        It checks for the model name in `/proc/device-tree/model`.

        Returns:
            The detected model name (e.g., 'KN-1010') or None if detection fails.
        """
        logging.info("Detecting Keenetic hardware model...")

        # Command to read the device model from the device tree
        command = "cat /proc/device-tree/model"
        stdout, stderr = self.ssh.execute_command(command)

        if stderr or not stdout:
            logging.error(f"Failed to detect hardware model. Error: {stderr or 'No output'}")
            return None

        model_string = stdout.strip()
        logging.info(f"Detected model string: '{model_string}'")

        # Find the corresponding model key in our hardware matrix
        for model_key, _ in KEENETIC_HARDWARE_MATRIX.items():
            if model_key in model_string:
                self.hardware_model = model_key
                self.hardware_specs = KEENETIC_HARDWARE_MATRIX[model_key]
                logging.info(f"Matched hardware model: {self.hardware_model}")
                logging.info(f"Loaded specs: {self.hardware_specs}")
                return self.hardware_model

        logging.warning(f"No matching hardware found in matrix for '{model_string}'")
        return None

    def get_dsl_register_address(self, register_name: str) -> int | None:
        """
        Calculates the absolute memory address for a given DSL register.

        Args:
            register_name: The name of the register (e.g., 'snr_margin').

        Returns:
            The absolute memory address as an integer, or None if the model
            is not detected or the register is not defined for the model.
        """
        if not self.hardware_specs:
            logging.error("Hardware specs not loaded. Run detect_hardware() first.")
            return None

        base = self.hardware_specs.get('register_base')
        offset = self.hardware_specs.get('dsl_registers', {}).get(register_name)

        if base is None or offset is None:
            logging.error(f"Register '{register_name}' not defined for model {self.hardware_model}")
            return None

        return base + offset

    def read_dsl_register(self, register_name: str) -> str | None:
        """
        Reads a value from a specific DSL register using devmem2 for direct memory access.

        Args:
            register_name: The symbolic name of the register to read.

        Returns:
            The value read from the register as a string, or None on failure.
        """
        address = self.get_dsl_register_address(register_name)
        if address is None:
            return None

        # Using devmem2 for direct hardware register access
        # This is a common tool in embedded Linux environments for this purpose
        command = f"devmem2 {hex(address)}"
        logging.info(f"Executing direct read from address {hex(address)}")

        stdout, stderr = self.ssh.execute_command(command)

        if stderr or "failed" in stdout.lower():
            logging.error(f"Failed to read from register '{register_name}' at {hex(address)}. Error: {stderr or stdout}")
            return None

        # Parse the output of devmem2, which is typically in the format:
        # "Value at address 0x... (0x...): 0x..."
        try:
            value = stdout.split(':')[-1].strip()
            logging.info(f"Successfully read value '{value}' from register '{register_name}'")
            return value
        except IndexError:
            logging.error(f"Could not parse devmem2 output: {stdout}")
            return None

    def write_dsl_register(self, register_name: str, value: str) -> bool:
        """
        Writes a value to a specific DSL register using devmem2.

        Args:
            register_name: The symbolic name of the register to write to.
            value: The value to write, typically in hexadecimal format (e.g., '0x100').

        Returns:
            True if the write was successful, False otherwise.
        """
        address = self.get_dsl_register_address(register_name)
        if address is None:
            return False

        # Using devmem2 to write to the register. 'w' specifies a word-sized write.
        command = f"devmem2 {hex(address)} w {value}"
        logging.info(f"Executing direct write to address {hex(address)} with value {value}")

        _, stderr = self.ssh.execute_command(command)

        if stderr:
            logging.error(f"Failed to write to register '{register_name}' at {hex(address)}. Error: {stderr}")
            return False

        logging.info(f"Successfully wrote '{value}' to register '{register_name}'")
        return True