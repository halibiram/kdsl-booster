import logging
from abc import ABC, abstractmethod
from src.entware_ssh import EntwareSSHInterface
from src.latency_optimizer import LatencyOptimizer

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

    @abstractmethod
    def get_line_stats(self) -> dict:
        """
        Retrieves key line statistics from the modem.
        Returns:
            A dictionary with stats like 'crc_errors', 'uptime', 'link_state'.
        """
        pass

    @abstractmethod
    def set_attenuation(self, downstream_attenuation: int, upstream_attenuation: int) -> bool:
        """
        Sets the downstream and upstream attenuation values.

        Args:
            downstream_attenuation: The target downstream attenuation in 0.1 dB.
            upstream_attenuation: The target upstream attenuation in 0.1 dB.
        Returns:
            True on success, False on failure.
        """
        pass

    @abstractmethod
    def set_loop_length(self, loop_length_m: int) -> bool:
        """
        Sets the virtual loop length.

        Args:
            loop_length_m: The target loop length in meters.
        Returns:
            True on success, False on failure.
        """
        pass

    @abstractmethod
    def set_signal_boost(self, boost_db: int) -> bool:
        """
        Applies a fake signal boost.

        Args:
            boost_db: The signal boost to apply in dB.
        Returns:
            True on success, False on failure.
        """
        pass

    @abstractmethod
    def set_pilot_tone_power(self, power_dbm: int) -> bool:
        """
        Manipulates the pilot tone power.

        Args:
            power_dbm: The target pilot tone power in dBm.
        Returns:
            True on success, False on failure.
        """
        pass

    @abstractmethod
    def set_psd_mask(self, mask_id: int) -> bool:
        """
        Sets the Power Spectral Density (PSD) mask.
        Args:
            mask_id: The identifier of the PSD mask to apply.
        Returns:
            True on success, False on failure.
        """
        pass

    @abstractmethod
    def set_upstream_power_boost(self, boost_db: int) -> bool:
        """
        Applies a power boost to the upstream signal.
        Args:
            boost_db: The power boost in dB.
        Returns:
            True on success, False on failure.
        """
        pass

    @abstractmethod
    def set_downstream_power_request(self, power_dbm: int) -> bool:
        """
        Manipulates the downstream power request.
        Args:
            power_dbm: The requested power in dBm.
        Returns:
            True on success, False on failure.
        """
        pass

    @abstractmethod
    def set_per_band_psd(self, band_config: dict) -> bool:
        """
        Sets per-band PSD shaping parameters.
        Args:
            band_config: A dictionary with band-specific PSD settings.
        Returns:
            True on success, False on failure.
        """
        pass

    @abstractmethod
    def set_vectoring_state(self, enabled: bool) -> bool:
        """
        Enables or disables vectoring (G.993.5) on the modem.
        Args:
            enabled: True to enable vectoring, False to disable.
        Returns:
            True on success, False on failure.
        """
        pass

    @abstractmethod
    def get_vectoring_pilot_sequence(self) -> list[int] | None:
        """
        Retrieves the vectoring pilot sequence data from the modem.
        This data is used for crosstalk analysis.
        Returns:
            A list of pilot sequence values, or None on failure.
        """
        pass

    @abstractmethod
    def get_bitloading_table(self) -> dict[int, int] | None:
        """
        Retrieves the bit-loading table (bits per tone).
        Returns:
            A dictionary mapping tone index to bits, or None on failure.
        """
        pass

    @abstractmethod
    def set_bitloading_table(self, bit_table: dict[int, int]) -> bool:
        """
        Applies a custom bit-loading table.
        Args:
            bit_table: A dictionary mapping tone index to the number of bits.
        Returns:
            True on success, False on failure.
        """
        pass

    @abstractmethod
    def set_tone_activation(self, tone_map: dict[int, bool]) -> bool:
        """
        Activates or deactivates specific tones.
        Args:
            tone_map: A dictionary mapping a tone index to a boolean (True=on, False=off).
        Returns:
            True on success, False on failure.
        """
        pass

    @abstractmethod
    def set_subcarrier_spacing(self, spacing_khz: float) -> bool:
        """
        Sets the sub-carrier spacing.
        Args:
            spacing_khz: The desired sub-carrier spacing in kHz.
        Returns:
            True on success, False on failure.
        """
        pass

    @abstractmethod
    def force_renegotiation(self) -> bool:
        """
        Forces the DSL line to renegotiate parameters (fast retrain).
        Returns:
            True on success, False on failure.
        """
        pass

    @abstractmethod
    def control_bitswap(self, enabled: bool) -> bool:
        """
        Enables or disables the bit-swap feature on the line.
        Args:
            enabled: True to enable bit-swapping, False to disable.
        Returns:
            True on success, False on failure.
        """
        pass

    @abstractmethod
    def run_selt(self) -> dict:
        """
        Initiates a Single-Ended Line Test (SELT) and returns the results.
        SELT provides information about line length and potential issues.
        Returns:
            A dictionary containing SELT results, such as line length and fault locations.
        """
        pass

    @abstractmethod
    def run_melt(self) -> dict:
        """
        Initiates a Metallic Line Test (MELT) to check physical line characteristics.
        This test usually requires the line to be in a non-operational state.
        Returns:
            A dictionary with measurements like voltage, resistance, and capacitance.
        """
        pass

    @abstractmethod
    def run_delt(self) -> dict:
        """
        Initiates a Dual-Ended Line Test (DELT).
        This is a comprehensive test that requires coordination with the DSLAM.
        Returns:
            A dictionary containing detailed line state information from both ends.
        """
        pass

    @abstractmethod
    def get_qln_data(self) -> dict[int, float] | None:
        """
        Retrieves the Quiet Line Noise (QLN) measurement on a per-tone basis.
        This represents the noise floor when the line is idle.
        Returns:
            A dictionary mapping tone index to noise power in dBm/Hz, or None on failure.
        """
        pass

    @abstractmethod
    def get_hlog_data(self) -> dict[int, float] | None:
        """
        Retrieves the Hlog data (per-tone channel characteristics/attenuation).
        Returns:
            A dictionary mapping tone index to attenuation in dB, or None on failure.
        """
        pass

    @abstractmethod
    def set_bonding_state(self, enabled: bool) -> bool:
        """
        Enables or disables G.998.x bonding on the modem.
        Args:
            enabled: True to enable bonding, False to disable.
        Returns:
            True on success, False on failure.
        """
        pass

    @abstractmethod
    def configure_bonding_group(self, group_id: int, mode: str, line_ids: list[int]) -> bool:
        """
        Configures a specific bonding group.
        Args:
            group_id: The identifier for the bonding group.
            mode: The bonding mode ('atm' or 'ethernet').
            line_ids: A list of physical line IDs to include in the group.
        Returns:
            True on success, False on failure.
        """
        pass

    @abstractmethod
    def set_bonding_differential_delay(self, delay_ms: int) -> bool:
        """
        Sets the differential delay compensation for a bonding group.
        Args:
            delay_ms: The maximum differential delay to compensate for, in milliseconds.
        Returns:
            True on success, False on failure.
        """
        pass

    @abstractmethod
    def set_interleaving(self, enabled: bool) -> bool:
        """
        Enables or disables interleaving (fast path).
        Args:
            enabled: True to enable interleaving, False for fast path.
        Returns:
            True on success, False on failure.
        """
        pass

    @abstractmethod
    def set_inp(self, value: int) -> bool:
        """
        Sets the Impulse Noise Protection (INP) value.
        Args:
            value: The target INP value.
        Returns:
            True on success, False on failure.
        """
        pass

    def set_latency_profile(self, profile: str) -> bool:
        """
        Applies a predefined latency optimization profile.
        Args:
            profile: The name of the profile ('fast', 'gaming', 'stable').
        Returns:
            True if the profile was applied successfully, False otherwise.
        """
        try:
            optimizer = LatencyOptimizer(self)
            optimizer.apply_profile(profile)
            logging.info(f"Successfully applied latency profile: {profile}")
            return True
        except (ValueError, NotImplementedError) as e:
            logging.error(f"Failed to apply latency profile '{profile}': {e}")
            return False

    @abstractmethod
    def get_link_status(self) -> str:
        """
        Retrieves the current link status of the DSL line.
        Common statuses include 'Up', 'Down', 'Training', 'Idle'.
        Returns:
            A string representing the link status.
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

    def get_line_stats(self) -> dict:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return {}

        command = f"{self.driver_path} info --stats"
        stdout, stderr = self.ssh.execute_command(command)

        if stderr or not stdout:
            logging.error(f"Failed to get Broadcom DSL stats: {stderr}")
            return {}

        stats = {}
        for line in stdout.splitlines():
            if "CRC" in line or "error" in line:
                try:
                    parts = line.split(':')
                    key = parts[0].strip().lower().replace(" ", "_")
                    value = int(parts[1].strip())
                    stats[key] = value
                except (IndexError, ValueError):
                    continue
        return stats

    def set_attenuation(self, downstream_attenuation: int, upstream_attenuation: int) -> bool:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return False

        command = f"{self.driver_path} configure --latn {downstream_attenuation} --uslatn {upstream_attenuation}"
        _, stderr = self.ssh.execute_command(command)

        if stderr:
            logging.error(f"Failed to set Broadcom attenuation: {stderr}")
            return False
        return True

    def set_loop_length(self, loop_length_m: int) -> bool:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return False

        command = f"{self.driver_path} configure --looplen {loop_length_m}"
        _, stderr = self.ssh.execute_command(command)

        if stderr:
            logging.error(f"Failed to set Broadcom loop length: {stderr}")
            return False
        return True

    def set_signal_boost(self, boost_db: int) -> bool:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return False

        # Assuming boost is an integer representing dB
        command = f"{self.driver_path} configure --sigboost {boost_db}"
        _, stderr = self.ssh.execute_command(command)

        if stderr:
            logging.error(f"Failed to set Broadcom signal boost: {stderr}")
            return False
        return True

    def set_pilot_tone_power(self, power_dbm: int) -> bool:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return False

        command = f"{self.driver_path} configure --pilottone {power_dbm}"
        _, stderr = self.ssh.execute_command(command)

        if stderr:
            logging.error(f"Failed to set Broadcom pilot tone power: {stderr}")
            return False
        return True

    def set_psd_mask(self, mask_id: int) -> bool:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return False

        command = f"{self.driver_path} configure --psdmask {mask_id}"
        _, stderr = self.ssh.execute_command(command)

        if stderr:
            logging.error(f"Failed to set Broadcom PSD mask: {stderr}")
            return False
        return True

    def set_upstream_power_boost(self, boost_db: int) -> bool:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return False

        command = f"{self.driver_path} configure --uspowerboost {boost_db}"
        _, stderr = self.ssh.execute_command(command)

        if stderr:
            logging.error(f"Failed to set Broadcom upstream power boost: {stderr}")
            return False
        return True

    def set_downstream_power_request(self, power_dbm: int) -> bool:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return False

        command = f"{self.driver_path} configure --dspowerreq {power_dbm}"
        _, stderr = self.ssh.execute_command(command)

        if stderr:
            logging.error(f"Failed to set Broadcom downstream power request: {stderr}")
            return False
        return True

    def set_per_band_psd(self, band_config: dict) -> bool:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return False

        config_str = " ".join([f"-band{k} {v}" for k, v in band_config.items()])
        command = f"{self.driver_path} configure --bandpsd {config_str}"
        _, stderr = self.ssh.execute_command(command)

        if stderr:
            logging.error(f"Failed to set Broadcom per-band PSD: {stderr}")
            return False
        return True

    def set_vectoring_state(self, enabled: bool) -> bool:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return False

        state = "on" if enabled else "off"
        command = f"{self.driver_path} configure --vectoring {state}"
        _, stderr = self.ssh.execute_command(command)

        if stderr:
            logging.error(f"Failed to set Broadcom vectoring state: {stderr}")
            return False
        logging.info(f"Broadcom vectoring state set to {state}.")
        return True

    def get_vectoring_pilot_sequence(self) -> list[int] | None:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return None

        command = f"{self.driver_path} info --show --pilots"
        stdout, stderr = self.ssh.execute_command(command)

        if stderr or not stdout:
            logging.error(f"Failed to get Broadcom vectoring pilots: {stderr}")
            return None

        try:
            # Assuming pilot data is a comma-separated list of integers
            pilots = [int(p.strip()) for p in stdout.split(',')]
            return pilots
        except ValueError:
            logging.error(f"Could not parse pilot sequence from output: {stdout}")
            return None

    def get_bitloading_table(self) -> dict[int, int] | None:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return None
        # Hypothetical command to dump bit-loading table in a 'tone:bits' format.
        command = f"{self.driver_path} info --show --bitloading"
        stdout, stderr = self.ssh.execute_command(command)
        if stderr or not stdout:
            logging.error(f"Failed to get Broadcom bit-loading table: {stderr}")
            return None
        try:
            table = {}
            for line in stdout.splitlines():
                parts = line.split(':')
                table[int(parts[0])] = int(parts[1])
            return table
        except (ValueError, IndexError):
            logging.error(f"Could not parse bit-loading table from output: {stdout}")
            return None

    def set_bitloading_table(self, bit_table: dict[int, int]) -> bool:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return False
        # The table is provided as a comma-separated list of 'tone:bits' pairs.
        table_str = ",".join([f"{tone}:{bits}" for tone, bits in bit_table.items()])
        command = f"{self.driver_path} configure --bitloading \"{table_str}\""
        logging.info(f"Applying custom bit-loading table to Broadcom chipset...")
        _, stderr = self.ssh.execute_command(command)
        if stderr:
            logging.error(f"Failed to set Broadcom bit-loading table: {stderr}")
            return False
        logging.info("Successfully applied bit-loading table.")
        return True

    def set_tone_activation(self, tone_map: dict[int, bool]) -> bool:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return False
        # Active tones are provided as a comma-separated list.
        # Inactive tones are those not in the list.
        active_tones = ",".join([str(tone) for tone, is_active in tone_map.items() if is_active])
        command = f"{self.driver_path} configure --activetones \"{active_tones}\""
        logging.info(f"Setting active tones on Broadcom chipset...")
        _, stderr = self.ssh.execute_command(command)
        if stderr:
            logging.error(f"Failed to set Broadcom tone activation: {stderr}")
            return False
        logging.info("Successfully applied tone activation map.")
        return True

    def set_subcarrier_spacing(self, spacing_khz: float) -> bool:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return False
        command = f"{self.driver_path} configure --spacing {spacing_khz}"
        _, stderr = self.ssh.execute_command(command)
        if stderr:
            logging.error(f"Failed to set Broadcom sub-carrier spacing: {stderr}")
            return False
        return True

    def force_renegotiation(self) -> bool:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return False
        # The 'restart' or 'retrain' command is common for this.
        # Using '--fast' often triggers a DRA event instead of a full resync.
        command = f"{self.driver_path} restart --fast"
        logging.info("Forcing fast renegotiation on Broadcom chipset...")
        _, stderr = self.ssh.execute_command(command)
        if stderr:
            logging.error(f"Failed to force Broadcom renegotiation: {stderr}")
            return False
        logging.info("Successfully triggered fast renegotiation.")
        return True

    def control_bitswap(self, enabled: bool) -> bool:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return False
        state = "on" if enabled else "off"
        command = f"{self.driver_path} configure --bitswap {state}"
        logging.info(f"Setting Broadcom bit-swap to {state}...")
        _, stderr = self.ssh.execute_command(command)
        if stderr:
            logging.error(f"Failed to set Broadcom bit-swap state: {stderr}")
            return False
        logging.info(f"Successfully set bit-swap state to {state}.")
        return True

    def run_selt(self) -> dict:
        logging.warning("SELT is not yet implemented for Broadcom HAL.")
        # Command might be: f"{self.driver_path} diag --selt"
        return {"status": "unsupported", "message": "SELT not implemented for this hardware."}

    def run_melt(self) -> dict:
        logging.warning("MELT is not yet implemented for Broadcom HAL.")
        # Command might be: f"{self.driver_path} diag --melt"
        return {"status": "unsupported", "message": "MELT not implemented for this hardware."}

    def run_delt(self) -> dict:
        logging.warning("DELT is not yet implemented for Broadcom HAL.")
        # Command might be: f"{self.driver_path} diag --delt"
        return {"status": "unsupported", "message": "DELT not implemented for this hardware."}

    def get_qln_data(self) -> dict[int, float] | None:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return None
        logging.warning("QLN data retrieval is not yet implemented for Broadcom HAL, returning mock data.")
        # Hypothetical command: f"{self.driver_path} info --show --qln"
        # Returning mock data for tones 0-10
        return {i: -135.0 + (i % 5) for i in range(10)}

    def get_hlog_data(self) -> dict[int, float] | None:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return None
        logging.warning("Hlog data retrieval is not yet implemented for Broadcom HAL, returning mock data.")
        # Hypothetical command: f"{self.driver_path} info --show --hlog"
        # Returning mock data for tones 0-10
        return {i: 5.0 + i * 0.5 for i in range(10)}

    def set_bonding_state(self, enabled: bool) -> bool:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return False
        state = "on" if enabled else "off"
        command = f"{self.driver_path} configure --bonding {state}"
        _, stderr = self.ssh.execute_command(command)
        if stderr:
            logging.error(f"Failed to set Broadcom bonding state: {stderr}")
            return False
        logging.info(f"Broadcom bonding state set to {state}.")
        return True

    def configure_bonding_group(self, group_id: int, mode: str, line_ids: list[int]) -> bool:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return False
        lines_str = ",".join(map(str, line_ids))
        command = f"{self.driver_path} bonding --configure-group {group_id} --mode {mode} --lines {lines_str}"
        _, stderr = self.ssh.execute_command(command)
        if stderr:
            logging.error(f"Failed to configure Broadcom bonding group: {stderr}")
            return False
        logging.info(f"Configured Broadcom bonding group {group_id} with mode {mode} and lines {lines_str}.")
        return True

    def set_bonding_differential_delay(self, delay_ms: int) -> bool:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return False
        command = f"{self.driver_path} bonding --set-delay {delay_ms}"
        _, stderr = self.ssh.execute_command(command)
        if stderr:
            logging.error(f"Failed to set Broadcom bonding differential delay: {stderr}")
            return False
        logging.info(f"Set Broadcom bonding differential delay to {delay_ms} ms.")
        return True

    def set_interleaving(self, enabled: bool) -> bool:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return False
        state = "on" if enabled else "off"
        command = f"{self.driver_path} configure --interleave {state}"
        _, stderr = self.ssh.execute_command(command)
        if stderr:
            logging.error(f"Failed to set Broadcom interleaving to {state}: {stderr}")
            return False
        logging.info(f"Broadcom interleaving set to {state}.")
        return True

    def set_inp(self, value: int) -> bool:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return False
        command = f"{self.driver_path} configure --inp {value}"
        _, stderr = self.ssh.execute_command(command)
        if stderr:
            logging.error(f"Failed to set Broadcom INP to {value}: {stderr}")
            return False
        logging.info(f"Broadcom INP set to {value}.")
        return True

    def get_link_status(self) -> str:
        if not self.driver_path:
            logging.error("Broadcom driver command not found.")
            return "Down"

        command = f"{self.driver_path} info --show"
        stdout, stderr = self.ssh.execute_command(command)

        if stderr or not stdout:
            logging.error(f"Failed to get Broadcom link status: {stderr}")
            return "Down"

        for line in stdout.splitlines():
            if "Status:" in line:
                try:
                    # e.g., "Status: Showtime"
                    return line.split(':')[1].strip().split(' ')[0]
                except IndexError:
                    continue
        return "Unknown"


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

    def get_line_stats(self) -> dict:
        if not self.driver_path:
            logging.error("Lantiq driver path not found.")
            return {}

        stats_path = f"{self.driver_path}/stats"
        stats = {}

        # List all stat files and read them
        command = f"find {stats_path} -type f -name '*'"
        files_stdout, _ = self.ssh.execute_command(command)

        if not files_stdout:
            logging.warning(f"No stat files found in {stats_path}")
            return {}

        for file_path in files_stdout.strip().split('\n'):
            if not file_path:
                continue

            key = file_path.split('/')[-1].lower()

            read_command = f"cat {file_path}"
            val_stdout, _ = self.ssh.execute_command(read_command)

            if val_stdout:
                try:
                    stats[key] = int(val_stdout.strip())
                except ValueError:
                    stats[key] = val_stdout.strip()

        return stats

    def set_attenuation(self, downstream_attenuation: int, upstream_attenuation: int) -> bool:
        if not self.driver_path:
            return False
        # Lantiq drivers often have separate files for downstream and upstream
        cmd_down = f"echo {downstream_attenuation} > {self.driver_path}/loop_attenuation_downstream"
        cmd_up = f"echo {upstream_attenuation} > {self.driver_path}/loop_attenuation_upstream"

        _, stderr_down = self.ssh.execute_command(cmd_down)
        _, stderr_up = self.ssh.execute_command(cmd_up)

        if stderr_down or stderr_up:
            logging.error(f"Failed to set Lantiq attenuation: DS({stderr_down}), US({stderr_up})")
            return False
        return True

    def set_loop_length(self, loop_length_m: int) -> bool:
        if not self.driver_path:
            return False
        command = f"echo {loop_length_m} > {self.driver_path}/loop_length_override"
        _, stderr = self.ssh.execute_command(command)
        if stderr:
            logging.error(f"Failed to set Lantiq loop length: {stderr}")
            return False
        return True

    def set_signal_boost(self, boost_db: int) -> bool:
        logging.error("Signal boost manipulation is not supported on Lantiq chipsets.")
        raise NotImplementedError("Lantiq HAL does not support set_signal_boost.")

    def set_pilot_tone_power(self, power_dbm: int) -> bool:
        logging.error("Pilot tone power manipulation is not supported on Lantiq chipsets.")
        raise NotImplementedError("Lantiq HAL does not support set_pilot_tone_power.")

    def set_psd_mask(self, mask_id: int) -> bool:
        if not self.driver_path:
            return False
        command = f"echo {mask_id} > {self.driver_path}/psd_mask_override"
        _, stderr = self.ssh.execute_command(command)
        if stderr:
            logging.error(f"Failed to set Lantiq PSD mask: {stderr}")
            return False
        return True

    def set_upstream_power_boost(self, boost_db: int) -> bool:
        if not self.driver_path:
            return False
        command = f"echo {boost_db} > {self.driver_path}/upstream_power_boost"
        _, stderr = self.ssh.execute_command(command)
        if stderr:
            logging.error(f"Failed to set Lantiq upstream power boost: {stderr}")
            return False
        return True

    def set_downstream_power_request(self, power_dbm: int) -> bool:
        if not self.driver_path:
            return False
        command = f"echo {power_dbm} > {self.driver_path}/downstream_power_request"
        _, stderr = self.ssh.execute_command(command)
        if stderr:
            logging.error(f"Failed to set Lantiq downstream power request: {stderr}")
            return False
        return True

    def set_per_band_psd(self, band_config: dict) -> bool:
        if not self.driver_path:
            return False
        # This is a simplified representation; a real implementation might need a more complex format.
        config_str = ";".join([f"{k}:{v}" for k, v in band_config.items()])
        command = f"echo '{config_str}' > {self.driver_path}/per_band_psd_config"
        _, stderr = self.ssh.execute_command(command)
        if stderr:
            logging.error(f"Failed to set Lantiq per-band PSD: {stderr}")
            return False
        return True

    def set_vectoring_state(self, enabled: bool) -> bool:
        if not self.driver_path:
            logging.error("Lantiq driver path not found.")
            return False

        state = "1" if enabled else "0"
        command = f"echo {state} > {self.driver_path}/vectoring_state"
        _, stderr = self.ssh.execute_command(command)

        if stderr:
            logging.error(f"Failed to set Lantiq vectoring state: {stderr}")
            return False

        logging.info(f"Lantiq vectoring state set to {'enabled' if enabled else 'disabled'}.")
        return True

    def get_vectoring_pilot_sequence(self) -> list[int] | None:
        if not self.driver_path:
            logging.error("Lantiq driver path not found.")
            return None

        command = f"cat {self.driver_path}/vectoring_pilots"
        stdout, stderr = self.ssh.execute_command(command)

        if stderr or not stdout:
            logging.error(f"Failed to get Lantiq vectoring pilots: {stderr}")
            return None

        try:
            # Assuming pilot data is a space-separated list of integers
            pilots = [int(p.strip()) for p in stdout.split()]
            return pilots
        except ValueError:
            logging.error(f"Could not parse pilot sequence from Lantiq output: {stdout}")
            return None

    def get_bitloading_table(self) -> dict[int, int] | None:
        if not self.driver_path:
            logging.error("Lantiq driver path not found.")
            return None
        # Hypothetical sysfs node for reading the bit-loading table.
        command = f"cat {self.driver_path}/bitloading_table"
        stdout, stderr = self.ssh.execute_command(command)
        if stderr or not stdout:
            logging.error(f"Failed to read Lantiq bit-loading table: {stderr}")
            return None
        try:
            table = {}
            for line in stdout.splitlines():
                parts = line.split()
                table[int(parts[0])] = int(parts[1])
            return table
        except (ValueError, IndexError):
            logging.error(f"Could not parse bit-loading table from Lantiq output: {stdout}")
            return None

    def set_bitloading_table(self, bit_table: dict[int, int]) -> bool:
        if not self.driver_path:
            logging.error("Lantiq driver path not found.")
            return False
        # The driver expects a string with one 'tone bits' pair per line.
        table_str = "\\n".join([f"{tone} {bits}" for tone, bits in bit_table.items()])
        command = f"echo -e \"{table_str}\" > {self.driver_path}/bitloading_table_override"
        logging.info("Applying custom bit-loading table to Lantiq chipset...")
        _, stderr = self.ssh.execute_command(command)
        if stderr:
            logging.error(f"Failed to set Lantiq bit-loading table: {stderr}")
            return False
        logging.info("Successfully applied bit-loading table.")
        return True

    def set_tone_activation(self, tone_map: dict[int, bool]) -> bool:
        if not self.driver_path:
            logging.error("Lantiq driver path not found.")
            return False
        # The driver expects a string with 'tone state' (1 for on, 0 for off) per line.
        map_str = "\\n".join([f"{tone} {'1' if is_active else '0'}" for tone, is_active in tone_map.items()])
        command = f"echo -e \"{map_str}\" > {self.driver_path}/tone_activation_override"
        logging.info("Applying tone activation map to Lantiq chipset...")
        _, stderr = self.ssh.execute_command(command)
        if stderr:
            logging.error(f"Failed to set Lantiq tone activation: {stderr}")
            return False
        logging.info("Successfully applied tone activation map.")
        return True

    def set_subcarrier_spacing(self, spacing_khz: float) -> bool:
        logging.error("Sub-carrier spacing manipulation is not typically supported on Lantiq chipsets.")
        raise NotImplementedError("Lantiq HAL does not support set_subcarrier_spacing.")

    def force_renegotiation(self) -> bool:
        if not self.driver_path:
            logging.error("Lantiq driver path not found.")
            return False
        command = f"echo 1 > {self.driver_path}/fast_retrain_trigger"
        logging.info("Forcing fast renegotiation on Lantiq chipset...")
        _, stderr = self.ssh.execute_command(command)
        if stderr:
            logging.error(f"Failed to force Lantiq renegotiation: {stderr}")
            return False
        logging.info("Successfully triggered fast renegotiation.")
        return True

    def control_bitswap(self, enabled: bool) -> bool:
        if not self.driver_path:
            logging.error("Lantiq driver path not found.")
            return False
        state = "1" if enabled else "0"
        command = f"echo {state} > {self.driver_path}/bitswap_control"
        logging.info(f"Setting Lantiq bit-swap to {'enabled' if enabled else 'disabled'}...")
        _, stderr = self.ssh.execute_command(command)
        if stderr:
            logging.error(f"Failed to set Lantiq bit-swap state: {stderr}")
            return False
        logging.info(f"Successfully set bit-swap state to {'enabled' if enabled else 'disabled'}.")
        return True

    def run_selt(self) -> dict:
        logging.warning("SELT is not yet implemented for Lantiq HAL.")
        # Command might be: f"echo 1 > {self.driver_path}/diag/selt_trigger"
        return {"status": "unsupported", "message": "SELT not implemented for this hardware."}

    def run_melt(self) -> dict:
        logging.warning("MELT is not yet implemented for Lantiq HAL.")
        # Command might be: f"echo 1 > {self.driver_path}/diag/melt_trigger"
        return {"status": "unsupported", "message": "MELT not implemented for this hardware."}

    def run_delt(self) -> dict:
        logging.warning("DELT is not yet implemented for Lantiq HAL.")
        # Command might be: f"echo 1 > {self.driver_path}/diag/delt_trigger"
        return {"status": "unsupported", "message": "DELT not implemented for this hardware."}

    def get_qln_data(self) -> dict[int, float] | None:
        if not self.driver_path:
            logging.error("Lantiq driver path not found.")
            return None
        logging.warning("QLN data retrieval is not yet implemented for Lantiq HAL, returning mock data.")
        # Hypothetical command: f"cat {self.driver_path}/diag/qln_data"
        # Returning mock data for tones 0-10
        return {i: -138.0 + (i % 5) for i in range(10)}

    def get_hlog_data(self) -> dict[int, float] | None:
        if not self.driver_path:
            logging.error("Lantiq driver path not found.")
            return None
        logging.warning("Hlog data retrieval is not yet implemented for Lantiq HAL, returning mock data.")
        # Hypothetical command: f"cat {self.driver_path}/diag/hlog_data"
        # Returning mock data for tones 0-10
        return {i: 4.0 + i * 0.6 for i in range(10)}

    def set_bonding_state(self, enabled: bool) -> bool:
        if not self.driver_path:
            logging.error("Lantiq driver path not found.")
            return False
        state = "1" if enabled else "0"
        command = f"echo {state} > {self.driver_path}/bonding_enable"
        _, stderr = self.ssh.execute_command(command)
        if stderr:
            logging.error(f"Failed to set Lantiq bonding state: {stderr}")
            return False
        logging.info(f"Lantiq bonding state set to {'enabled' if enabled else 'disabled'}.")
        return True

    def configure_bonding_group(self, group_id: int, mode: str, line_ids: list[int]) -> bool:
        if not self.driver_path:
            logging.error("Lantiq driver path not found.")
            return False
        lines_str = ",".join(map(str, line_ids))
        # Example: echo "0,atm,0,1" > /sys/class/dsl/dsl0/bonding_group_config
        command = f"echo '{group_id},{mode},{lines_str}' > {self.driver_path}/bonding_group_config"
        _, stderr = self.ssh.execute_command(command)
        if stderr:
            logging.error(f"Failed to configure Lantiq bonding group: {stderr}")
            return False
        logging.info(f"Configured Lantiq bonding group {group_id}.")
        return True

    def set_bonding_differential_delay(self, delay_ms: int) -> bool:
        if not self.driver_path:
            logging.error("Lantiq driver path not found.")
            return False
        command = f"echo {delay_ms} > {self.driver_path}/bonding_differential_delay_max"
        _, stderr = self.ssh.execute_command(command)
        if stderr:
            logging.error(f"Failed to set Lantiq bonding differential delay: {stderr}")
            return False
        logging.info(f"Set Lantiq bonding differential delay to {delay_ms} ms.")
        return True

    def set_interleaving(self, enabled: bool) -> bool:
        if not self.driver_path:
            logging.error("Lantiq driver path not found.")
            return False
        state = "1" if enabled else "0"
        command = f"echo {state} > {self.driver_path}/interleaving_control"
        _, stderr = self.ssh.execute_command(command)
        if stderr:
            logging.error(f"Failed to set Lantiq interleaving state: {stderr}")
            return False
        logging.info(f"Lantiq interleaving set to {'enabled' if enabled else 'disabled'}.")
        return True

    def set_inp(self, value: int) -> bool:
        if not self.driver_path:
            logging.error("Lantiq driver path not found.")
            return False
        command = f"echo {value} > {self.driver_path}/inp_control"
        _, stderr = self.ssh.execute_command(command)
        if stderr:
            logging.error(f"Failed to set Lantiq INP value: {stderr}")
            return False
        logging.info(f"Lantiq INP set to {value}.")
        return True

    def get_link_status(self) -> str:
        if not self.driver_path:
            logging.error("Lantiq driver path not found.")
            return "Down"

        command = f"cat {self.driver_path}/link_status"
        stdout, stderr = self.ssh.execute_command(command)

        if stderr or not stdout:
            logging.error(f"Failed to read Lantiq link status: {stderr}")
            return "Down"

        # The status is usually a single word, e.g., "Up", "Training", "Down"
        return stdout.strip()


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
            return self.hal_class

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