"""
This module contains the core logic for DSL parameter spoofing.

It includes physics-based models for calculating realistic target values for
parameters like attenuation and SNR. It also provides the high-level classes
that orchestrate the manipulation of kernel parameters to achieve the desired
line performance.
"""
import time
import time
import logging
import numpy as np

from src.crosstalk_simulator import CrosstalkSimulator
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

    def apply_psd_mask_override(self, mask_id: int) -> bool:
        """
        Applies a specific PSD mask by its ID.
        Args:
            mask_id: The ID of the PSD mask to apply.
        Returns:
            True if the command was sent successfully, False otherwise.
        """
        logging.info(f"Applying PSD mask override: ID {mask_id}")
        success = self.hal.set_psd_mask(mask_id)
        if success:
            logging.info("Successfully applied PSD mask override.")
        else:
            logging.error("Failed to apply PSD mask override.")
        return success

    def apply_upstream_power_boost(self, boost_db: int) -> bool:
        """
        Applies a power boost to the upstream signal.
        Args:
            boost_db: The power boost in dB.
        Returns:
            True if the command was sent successfully, False otherwise.
        """
        logging.info(f"Applying upstream power boost: {boost_db} dB")
        success = self.hal.set_upstream_power_boost(boost_db)
        if success:
            logging.info("Successfully applied upstream power boost.")
        else:
            logging.error("Failed to apply upstream power boost.")
        return success

    def manipulate_downstream_power_request(self, power_dbm: int) -> bool:
        """
        Manipulates the downstream power request sent by the modem.
        Args:
            power_dbm: The requested power in dBm.
        Returns:
            True if the command was sent successfully, False otherwise.
        """
        logging.info(f"Manipulating downstream power request: {power_dbm} dBm")
        success = self.hal.set_downstream_power_request(power_dbm)
        if success:
            logging.info("Successfully manipulated downstream power request.")
        else:
            logging.error("Failed to manipulate downstream power request.")
        return success

    def optimize_per_band_psd(self, band_config: dict) -> bool:
        """
        Applies a custom per-band PSD configuration.
        Args:
            band_config: A dictionary defining the PSD for each band.
        Returns:
            True if the command was sent successfully, False otherwise.
        """
        logging.info(f"Applying per-band PSD optimization: {band_config}")
        success = self.hal.set_per_band_psd(band_config)
        if success:
            logging.info("Successfully applied per-band PSD optimization.")
        else:
            logging.error("Failed to apply per-band PSD optimization.")
        return success

    def start_dynamic_psd_adaptation(self, monitoring_duration_s: int = 300, check_interval_s: int = 10, instability_threshold: int = 50) -> dict:
        """
        Monitors line for instability and adaptively adjusts upstream power.
        This uses CRC errors as a proxy for line instability, which can be caused
        by factors like crosstalk. A more advanced implementation would use a direct
        crosstalk metric if available from the hardware.

        Args:
            monitoring_duration_s: Total time to run the adaptive loop.
            check_interval_s: How often to check line stats.
            instability_threshold: Number of new CRC errors per interval that triggers a power reduction.
        Returns:
            A dictionary with the final results of the adaptation.
        """
        logging.info("Starting dynamic PSD adaptation based on line instability (CRC errors)...")
        start_time = time.time()
        end_time = start_time + monitoring_duration_s

        initial_stats = self.hal.get_line_stats()
        last_crc_errors = initial_stats.get('crc_errors', 0)

        current_boost = 0  # Start with a baseline boost of 0 dB.

        while time.time() < end_time:
            current_stats = self.hal.get_line_stats()
            current_crc_errors = current_stats.get('crc_errors', 0)
            new_errors = current_crc_errors - last_crc_errors

            logging.info(f"Current Upstream Power Boost: {current_boost} dB. New CRC errors: {new_errors}")

            if new_errors > instability_threshold:
                # High instability detected, reduce our power to stabilize the line.
                current_boost = max(0, current_boost - 1)  # Decrease boost, not going below 0.
                logging.warning(f"Instability ({new_errors} errors) exceeded threshold. Reducing power boost to {current_boost} dB.")
                self.hal.set_upstream_power_boost(current_boost)
            else:
                # Line is stable, we can be more aggressive.
                current_boost += 1
                logging.info(f"Line is stable. Increasing power boost to {current_boost} dB.")
                self.hal.set_upstream_power_boost(current_boost)

            last_crc_errors = current_crc_errors
            time.sleep(check_interval_s)

        logging.info(f"Dynamic PSD adaptation finished. Final power boost: {current_boost} dB.")
        return {"success": True, "final_upstream_power_boost": current_boost}

    def join_vectoring_group(self, interface: str = 'dsl0') -> bool:
        """
        Joins a vectoring group by enabling vectoring in the HAL and spoofing
        the G.hs handshake to advertise vectoring capabilities.

        Args:
            interface (str): The network interface for G.hs injection.

        Returns:
            bool: True if both operations were successful, False otherwise.
        """
        logging.info("Attempting to join vectoring group...")

        # 1. Enable vectoring at the hardware level via the HAL
        hal_success = self.hal.set_vectoring_state(enabled=True)
        if not hal_success:
            logging.error("Failed to enable vectoring state in the HAL. Aborting join.")
            return False

        # 2. Spoof the handshake to advertise vectoring support
        # This ensures the DSLAM sees us as vectoring-capable from the start.
        handshake_spoofer = GHSHandshakeSpoofer(self.dsl_interface_factory.ssh)
        handshake_success = handshake_spoofer.craft_and_inject_fake_capabilities(
            interface=interface,
            force_vectoring=True
        )

        if not handshake_success:
            logging.error("Failed to inject spoofed G.hs capabilities for vectoring.")
            # Optional: could try to roll back the HAL change here.
            # self.hal.set_vectoring_state(enabled=False)
            return False

        logging.info("Successfully joined vectoring group (HAL enabled and handshake spoofed).")
        return True

    def leave_vectoring_group(self) -> bool:
        """
        Leaves a vectoring group by disabling vectoring in the HAL.

        Returns:
            bool: True if the operation was successful, False otherwise.
        """
        logging.info("Attempting to leave vectoring group...")
        success = self.hal.set_vectoring_state(enabled=False)
        if success:
            logging.info("Successfully left vectoring group (HAL disabled).")
        else:
            logging.error("Failed to disable vectoring state in the HAL.")

        return success

    def mitigate_crosstalk(self, aggressor_count: int = 2, mode: str = 'snr') -> bool:
        """
        Simulates crosstalk from a number of aggressors and attempts to mitigate
        it by adjusting line parameters.

        Args:
            aggressor_count (int): The number of interfering lines to simulate.
            mode (str): The mitigation strategy to use ('snr' or 'power').

        Returns:
            bool: True if a mitigation action was successfully applied.
        """
        logging.info(f"Starting crosstalk mitigation simulation for {aggressor_count} aggressors...")

        # 1. Simulate the crosstalk noise profile.
        simulator = CrosstalkSimulator(aggressor_count=aggressor_count)
        fext_profile = simulator.generate_fext_profile()
        total_fext_power = np.sum(fext_profile)

        logging.info(f"Simulated total FEXT power: {total_fext_power:.2e} W/Hz")

        # 2. Apply a mitigation strategy based on the simulated noise.
        if mode == 'snr':
            # Strategy: Increase the target SNR margin to create more headroom against the noise.
            # This is a simplified heuristic: add 1 dB of margin for every 1e-18 W/Hz of noise.
            current_snr = self.hal.get_snr_margin()
            if current_snr is None:
                logging.error("Cannot apply SNR mitigation: failed to get current SNR.")
                return False

            snr_increase = int(total_fext_power / 1e-18)
            target_snr = current_snr + snr_increase

            logging.info(f"Mitigation: increasing SNR margin by {snr_increase} dB to a target of {target_snr:.1f} dB.")
            # Value must be converted to 0.1 dB for the HAL
            return self.hal.set_snr_margin(int(target_snr * 10))

        elif mode == 'power':
            # Strategy: Boost upstream power to "shout over" the noise.
            # Heuristic: increase power by 1 dB for every 2e-18 W/Hz of noise.
            power_boost = int(total_fext_power / 2e-18)
            logging.info(f"Mitigation: applying upstream power boost of {power_boost} dB.")
            return self.hal.set_upstream_power_boost(power_boost)

        else:
            logging.error(f"Unknown mitigation mode: {mode}. Supported modes are 'snr' and 'power'.")
            return False

    def set_per_tone_bit_loading(self, bit_allocation: dict[int, int]) -> bool:
        """
        Applies a custom bit-loading map to specific tones.

        Args:
            bit_allocation: A dictionary where keys are tone indices and values are
                            the number of bits to load (0-15).

        Returns:
            True if the bit-loading table was successfully applied, False otherwise.
        """
        logging.info(f"Applying custom bit-loading for {len(bit_allocation)} tones...")
        if not all(0 <= bits <= 15 for bits in bit_allocation.values()):
            logging.error("Invalid bit allocation: bits per tone must be between 0 and 15.")
            return False

        try:
            success = self.hal.set_bitloading_table(bit_allocation)
            if success:
                logging.info("Successfully applied custom bit-loading table.")
            else:
                logging.error("HAL failed to apply the bit-loading table.")
            return success
        except NotImplementedError:
            logging.error(f"Bit-loading manipulation is not supported by the {self.hal.__class__.__name__} HAL.")
            return False

    def manipulate_tone_ordering(self, tone_order: list[int]) -> bool:
        """
        Manipulates the tone ordering to force the use of specific tones first.
        Note: This is a highly advanced and often unsupported feature. The implementation
        here assumes a hypothetical HAL method.

        Args:
            tone_order: A list of tone indices in the desired order of usage.

        Returns:
            True if the tone reordering was successful, False otherwise.
        """
        logging.info(f"Applying custom tone ordering, starting with tone {tone_order[0]}...")
        try:
            # This assumes a hypothetical HAL function `set_tone_order`
            # which is not standard. We are adding it for feature completeness.
            if hasattr(self.hal, 'set_tone_order'):
                success = self.hal.set_tone_order(tone_order)
                if success:
                    logging.info("Successfully applied custom tone ordering.")
                else:
                    logging.error("HAL failed to apply the custom tone order.")
                return success
            else:
                logging.error(f"Tone ordering is not supported by the {self.hal.__class__.__name__} HAL.")
                return False
        except NotImplementedError:
            logging.error(f"Tone ordering is not supported by the {self.hal.__class__.__name__} HAL.")
            return False

    def control_tone_activation(self, tones_to_disable: list[int] | None = None, tones_to_enable: list[int] | None = None) -> bool:
        """
        Activates or deactivates specific DMT tones.

        Args:
            tones_to_disable: A list of tone indices to turn off.
            tones_to_enable: A list of tone indices to turn on.

        Returns:
            True if the tone activation map was successfully applied, False otherwise.
        """
        logging.info(f"Controlling tone activation: Disable {tones_to_disable}, Enable {tones_to_enable}")

        # This is a simplified approach. A real implementation would need to read
        # the current tone map first. For this example, we assume we start from a
        # default state where all tones are on.

        # Since we don't know the full set of tones, we create a map just for the changes.
        tone_map = {}
        if tones_to_disable:
            for tone in tones_to_disable:
                tone_map[tone] = False
        if tones_to_enable:
            for tone in tones_to_enable:
                tone_map[tone] = True

        if not tone_map:
            logging.warning("No tones specified for activation or deactivation.")
            return True

        try:
            success = self.hal.set_tone_activation(tone_map)
            if success:
                logging.info("Successfully applied tone activation changes.")
            else:
                logging.error("HAL failed to apply tone activation changes.")
            return success
        except NotImplementedError:
            logging.error(f"Tone activation is not supported by the {self.hal.__class__.__name__} HAL.")
            return False

    def manipulate_subcarrier_spacing(self, spacing_khz: float) -> bool:
        """
        Manipulates the sub-carrier spacing.

        Args:
            spacing_khz: The desired sub-carrier spacing in kHz (e.g., 4.3125 or 8.625).

        Returns:
            True if the spacing was successfully set, False otherwise.
        """
        logging.info(f"Setting sub-carrier spacing to {spacing_khz} kHz...")
        try:
            success = self.hal.set_subcarrier_spacing(spacing_khz)
            if success:
                logging.info(f"Successfully set sub-carrier spacing to {spacing_khz} kHz.")
            else:
                logging.error("HAL failed to set the sub-carrier spacing.")
            return success
        except NotImplementedError:
            logging.error(f"Sub-carrier spacing manipulation is not supported by the {self.hal.__class__.__name__} HAL.")
            return False

    def optimize_tone_allocation(self, target_distance_m: int, snr_threshold_db: float = 6.0) -> bool:
        """
        Analyzes the line for a simulated distance, calculates an optimal bit and
        tone allocation based on the physics model, and applies it.

        Args:
            target_distance_m: The simulated line distance to optimize for.
            snr_threshold_db: The minimum SNR for a tone to be considered usable.

        Returns:
            True if the optimization was successfully applied, False otherwise.
        """
        logging.info(f"Optimizing tone allocation for a simulated distance of {target_distance_m}m...")

        # 1. Calculate the SNR profile and get corresponding tone indices.
        snr_per_tone = self.physics.calculate_snr_per_tone(distance_m=target_distance_m)
        tone_indices = self.physics.get_tone_indices()

        if len(snr_per_tone) != len(tone_indices):
            logging.error("Mismatch between SNR profile and tone indices. Aborting optimization.")
            return False

        # 2. Determine bit allocation and which tones to deactivate based on the model.
        bit_allocation = {}
        tones_to_deactivate = []

        # Calculate bits per tone using the same Shannon-Hartley logic as in the physics model.
        snr_gap_linear = 10 ** (self.physics.SNR_GAP_DB / 10)
        effective_snr_linear = (10 ** (snr_per_tone / 10)) / snr_gap_linear

        bits_per_tone = np.zeros_like(effective_snr_linear)
        positive_snr_mask = effective_snr_linear > 0
        bits_per_tone[positive_snr_mask] = np.log2(1 + effective_snr_linear[positive_snr_mask])

        # Apply the 15-bit cap and floor to get a realistic integer value.
        bits_per_tone = np.clip(bits_per_tone, 0, self.physics.MAX_BITS_PER_TONE)
        final_bits_per_tone = np.floor(bits_per_tone).astype(int)

        for i, snr in enumerate(snr_per_tone):
            tone_index = tone_indices[i]
            if snr < snr_threshold_db:
                # If SNR is too low, deactivate the tone and assign 0 bits.
                tones_to_deactivate.append(tone_index)
                bit_allocation[tone_index] = 0
            else:
                # Otherwise, assign the calculated number of bits.
                bit_allocation[tone_index] = final_bits_per_tone[i]

        logging.info(f"Optimization plan: Deactivate {len(tones_to_deactivate)} tones, apply custom bit-loading.")

        # 3. Apply the new configuration via the HAL.
        success_activation = True
        if tones_to_deactivate:
            success_activation = self.control_tone_activation(tones_to_disable=tones_to_deactivate)

        if not success_activation:
            logging.error("Failed to deactivate tones. Aborting further optimization.")
            return False

        logging.info("Applying optimized bit-loading table...")
        success_bitload = self.set_per_tone_bit_loading(bit_allocation)

        if success_bitload:
            logging.info("Successfully applied tone allocation optimization.")
        else:
            logging.error("Failed to apply tone allocation optimization.")

        return success_bitload