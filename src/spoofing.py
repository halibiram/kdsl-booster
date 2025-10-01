"""
This module contains the core logic for DSL parameter spoofing.

It includes physics-based models for calculating realistic target values for
parameters like attenuation and SNR. It also provides the high-level classes
that orchestrate the manipulation of kernel parameters to achieve the desired
line performance.
"""
import time
import logging
import numpy as np

from src.entware_ssh import EntwareSSHInterface
from src.keenetic_dsl_interface import KeeneticDSLInterface
from src.advanced_dsl_physics import AdvancedDSLPhysics
from src.ghs_packet_crafter import craft_fake_cl_message


class GHSHandshakeSpoofer:
    """
    Handles the crafting and injection of malicious G.hs handshake packets
    to manipulate the DSL connection at the protocol level.
    """

    def __init__(self, ssh_interface: EntwareSSHInterface):
        """
        Initializes the spoofer with an SSH interface.

        Args:
            ssh_interface: An active EntwareSSHInterface instance.
        """
        self.ssh = ssh_interface

    def craft_and_inject_fake_capabilities(
        self,
        interface: str = 'dsl0',
        vendor_id: bytes = b'FAKE_CPE',
        profile_35b: bool = True,
        force_vectoring: bool = True
    ) -> bool:
        """
        Crafts a fake G.hs CL (Capabilities List) message and injects it.

        Args:
            interface: The network interface to inject on (e.g., 'dsl0').
            vendor_id: The fake vendor ID to advertise.
            profile_35b: Whether to advertise support for VDSL2 profile 35b.
            force_vectoring: Whether to advertise support for G.vector.

        Returns:
            True if the injection command was sent, False otherwise.
        """
        print("Crafting malicious G.hs capabilities message...")
        packet_bytes = craft_fake_cl_message(
            vendor_id=vendor_id,
            profile_35b=profile_35b,
            force_vectoring=force_vectoring
        )

        print(f"Attempting to inject {len(packet_bytes)} bytes onto interface {interface}...")
        success = self.ssh.inject_raw_packet(interface, packet_bytes)

        if success:
            print("Successfully sent spoofed capabilities packet.")
        else:
            print("Failed to inject spoofed capabilities packet.")

        return success


class KernelDSLManipulator:
    """
    Orchestrates the end-to-end process of calculating and applying spoofed parameters
    using advanced, physics-based models.
    """

    def __init__(self, ssh_interface: EntwareSSHInterface, profile: str = '17a'):
        """
        Initializes the manipulator, gets the correct hardware abstraction layer (HAL),
        and sets up advanced physics models.

        Args:
            ssh_interface: An active EntwareSSHInterface instance.
            profile: The VDSL2 profile to use for physics calculations (e.g., '17a').
        """
        self.dsl_interface_factory = KeeneticDSLInterface(ssh_interface)
        self.hal = self.dsl_interface_factory.get_hal()
        self.physics = AdvancedDSLPhysics(profile=profile)

        if not self.hal:
            raise RuntimeError("Failed to detect Keenetic hardware or initialize HAL. Cannot proceed.")

    def _find_optimal_snr_for_rate(self, target_rate_mbps: float, distance_m: int) -> float:
        """
        Performs an iterative search to find the minimum SNR required for the target rate.
        This is an inverse of the Shannon-Hartley calculation.
        """
        low_snr, high_snr = 0.0, 60.0  # A reasonable search range for SNR in dB
        optimal_snr = high_snr

        for _ in range(10):  # 10 iterations of binary search for good precision
            mid_snr = (low_snr + high_snr) / 2
            calculated_rate = self.physics.calculate_max_bitrate(mid_snr, distance_m)

            if calculated_rate >= target_rate_mbps:
                optimal_snr = mid_snr  # This SNR is a potential candidate
                high_snr = mid_snr      # Try for an even lower SNR
            else:
                low_snr = mid_snr      # This SNR is too low, need to aim higher

        return round(optimal_snr, 1)

    def set_target_profile(
        self, target_rate_mbps: float, target_distance_m: int
    ) -> dict:
        """
        Calculates and applies a new DSL profile based on a spoofed distance.

        Args:
            target_rate_mbps: The desired data rate (used for experimentation).
            target_distance_m: The simulated target distance in meters.

        Returns:
            A dictionary reporting success and including the parameters for training.
        """
        print(f"Setting target profile for {self.hal.__class__.__name__}: {target_rate_mbps} Mbps at {target_distance_m}m")

        # 1. Calculate the physical parameters that correspond to the spoofed distance.
        snrs_per_tone = self.physics.calculate_snr_per_tone(distance_m=target_distance_m)
        target_snr = np.mean(snrs_per_tone)

        attenuations_per_tone = self.physics.model_attenuation_per_tone(distance_m=target_distance_m)
        target_attenuation = np.mean(attenuations_per_tone)

        snr_register_value = int(target_snr * 10)
        print(f"Calculated Targets for {target_distance_m}m -> Avg SNR: {target_snr:.1f} dB, Avg Attenuation: {target_attenuation:.2f} dB")

        # 2. Write the new physical parameters to the hardware via the HAL.
        # The HAL methods expect values in specific units (e.g., 0.1 dB).
        snr_success = self.hal.set_snr_margin(snr_register_value)

        # Convert target attenuation to 0.1 dB for the HAL. Assume same for US/DS for now.
        attenuation_register_value = int(target_attenuation * 10)
        attenuation_success = self.hal.set_attenuation(
            downstream_attenuation=attenuation_register_value,
            upstream_attenuation=attenuation_register_value
        )

        results = {
            "snr_margin_set": snr_success,
            "attenuation_set": attenuation_success,
            "applied_snr_db": target_snr if snr_success else 0,
            "applied_attenuation_db": target_attenuation if attenuation_success else 0,
        }

        print(f"Manipulation results: {results}")
        return results

    def dynamically_reduce_snr(self, target_snr_floor_db: float, step_db: float = 0.5, step_interval_s: int = 5) -> dict:
        """
        Gradually reduces the SNR margin from its current value to a target floor.

        Args:
            target_snr_floor_db: The lowest SNR margin to attempt.
            step_db: The amount to decrease the SNR by in each step (in dB).
            step_interval_s: The time to wait between decrements.

        Returns:
            A dictionary reporting the final state.
        """
        logging.info("Starting dynamic SNR margin reduction...")
        current_snr = self.hal.get_snr_margin()
        if current_snr is None:
            logging.error("Could not retrieve initial SNR margin. Aborting.")
            return {"success": False, "final_snr": None}

        logging.info(f"Initial SNR: {current_snr:.1f} dB. Target floor: {target_snr_floor_db:.1f} dB.")

        final_snr = current_snr
        for target_snr in np.arange(current_snr, target_snr_floor_db - step_db, -step_db):
            logging.info(f"Setting SNR margin to {target_snr:.1f} dB...")
            snr_register_value = int(target_snr * 10)
            success = self.hal.set_snr_margin(snr_register_value)
            if not success:
                logging.error(f"Failed to set SNR to {target_snr:.1f} dB. Stopping reduction.")
                break
            final_snr = target_snr
            logging.info(f"Waiting for {step_interval_s} seconds...")
            time.sleep(step_interval_s)

        logging.info(f"Dynamic SNR reduction finished. Final SNR margin: {final_snr:.1f} dB.")
        return {"success": True, "final_snr": final_snr}

    def adapt_to_line_quality(self, monitoring_duration_s: int = 300, check_interval_s: int = 10, crc_error_threshold: int = 5) -> dict:
        """
        Monitors line quality and adaptively adjusts the SNR margin.

        Args:
            monitoring_duration_s: Total time to run the adaptive loop.
            check_interval_s: How often to check line stats.
            crc_error_threshold: Number of new CRC errors per interval that triggers an SNR increase.

        Returns:
            A dictionary with the final results of the adaptation.
        """
        logging.info("Starting adaptive SNR adjustment based on line quality...")
        start_time = time.time()
        end_time = start_time + monitoring_duration_s

        initial_stats = self.hal.get_line_stats()
        last_crc_errors = initial_stats.get('crc_errors', 0)

        while time.time() < end_time:
            current_snr = self.hal.get_snr_margin()
            if current_snr is None:
                logging.warning("Could not get current SNR. Skipping adjustment cycle.")
                time.sleep(check_interval_s)
                continue

            current_stats = self.hal.get_line_stats()
            current_crc_errors = current_stats.get('crc_errors', 0)
            new_errors = current_crc_errors - last_crc_errors

            logging.info(f"Current SNR: {current_snr:.1f} dB. New CRC errors in last {check_interval_s}s: {new_errors}")

            target_snr = current_snr
            if new_errors > crc_error_threshold:
                # Line is unstable, increase SNR margin to stabilize
                target_snr += 1.0  # Increase by 1 dB for stability
                logging.warning(f"CRC errors ({new_errors}) exceeded threshold ({crc_error_threshold}). Increasing SNR to {target_snr:.1f} dB.")
            else:
                # Line is stable, try to push for more performance
                target_snr -= 0.2  # Cautiously decrease by 0.2 dB
                logging.info(f"Line is stable. Cautiously decreasing SNR to {target_snr:.1f} dB.")

            snr_register_value = int(target_snr * 10)
            self.hal.set_snr_margin(snr_register_value)

            last_crc_errors = current_crc_errors
            time.sleep(check_interval_s)

        final_snr = self.hal.get_snr_margin()
        logging.info(f"Adaptive SNR adjustment finished. Final SNR: {final_snr:.1f} dB.")
        return {"success": True, "final_snr": final_snr}

    def apply_loop_length_manipulation(self, target_distance_m: int) -> bool:
        """
        Attempts to directly manipulate the loop length reported by the modem.

        Args:
            target_distance_m: The spoofed loop length in meters.

        Returns:
            True if the command was sent successfully, False otherwise.
        """
        logging.info(f"Applying direct loop length manipulation: {target_distance_m}m")
        success = self.hal.set_loop_length(target_distance_m)
        if success:
            logging.info("Successfully applied loop length manipulation.")
        else:
            logging.error("Failed to apply loop length manipulation.")
        return success

    def apply_fake_signal_boost(self, boost_db: int) -> bool:
        """
        Applies a fake signal boost indicator.

        Args:
            boost_db: The fake signal boost to apply in dB.

        Returns:
            True if the command was sent successfully, False otherwise.
        """
        logging.info(f"Applying fake signal boost: {boost_db} dB")
        success = self.hal.set_signal_boost(boost_db)
        if success:
            logging.info("Successfully applied fake signal boost.")
        else:
            logging.error("Failed to apply fake signal boost.")
        return success

    def apply_pilot_tone_manipulation(self, power_dbm: int) -> bool:
        """
        Manipulates the reported power of pilot tones.

        Args:
            power_dbm: The target power for pilot tones in dBm.

        Returns:
            True if the command was sent successfully, False otherwise.
        """
        logging.info(f"Applying pilot tone power manipulation: {power_dbm} dBm")
        success = self.hal.set_pilot_tone_power(power_dbm)
        if success:
            logging.info("Successfully applied pilot tone power manipulation.")
        else:
            logging.error("Failed to apply pilot tone power manipulation.")
        return success