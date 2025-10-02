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

from src.entware_ssh import EntwareSSHInterface
from src.keenetic_dsl_interface import KeeneticDSLInterface
from src.advanced_dsl_physics import AdvancedDSLPhysics
from src.ghs_packet_crafter import craft_fake_cl_message
from src.sra_controller import SRAController
from src.bonding_exploiter import BondingExploiter


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
        self.bonding_exploiter = BondingExploiter(self.hal) if self.hal else None

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

    def adapt_to_line_quality(self, monitoring_duration_s: int = 300) -> dict:
        """
        Initializes and runs the SRA controller to manage the line.

        Args:
            monitoring_duration_s: Total time to run the adaptive SRA controller.

        Returns:
            A dictionary with the final results of the adaptation.
        """
        logging.info("Handing over control to the SRA controller...")
        controller = SRAController(self.hal)
        controller.start(duration_s=monitoring_duration_s)

        # The controller has finished its run. We can report the final state.
        final_snr = self.hal.get_snr_margin()
        final_power_boost = controller.current_power_boost_db
        logging.info(f"SRA run finished. Final SNR: {final_snr:.1f} dB, Final Power Boost: {final_power_boost} dB.")

        return {
            "success": True,
            "final_snr": final_snr,
            "final_power_boost_db": final_power_boost,
        }

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

    def mitigate_crosstalk(self, distance_m: int, aggressor_count: int = 2, mode: str = 'snr') -> bool:
        """
        Calculates the impact of crosstalk from a number of aggressors and attempts
        to mitigate it by adjusting line parameters.

        Args:
            distance_m: The line distance in meters, required for accurate FEXT calculation.
            aggressor_count (int): The number of interfering lines to simulate.
            mode (str): The mitigation strategy to use ('snr' or 'power').

        Returns:
            bool: True if a mitigation action was successfully applied.
        """
        logging.info(f"Starting crosstalk mitigation for {aggressor_count} aggressors at {distance_m}m...")

        # 1. Calculate the FEXT noise Power Spectral Density using the physics model.
        fext_psd_dbm_hz = self.physics.model_fext_noise_psd(
            n_disturbers=aggressor_count,
            distance_m=distance_m
        )

        # 2. Convert PSD from dBm/Hz to total power in mW to get a single metric for the heuristic.
        fext_power_per_tone_mw = (10**(fext_psd_dbm_hz / 10)) * self.physics.tone_spacing
        total_fext_power_mw = np.sum(fext_power_per_tone_mw)

        logging.info(f"Calculated total FEXT power: {total_fext_power_mw:.4f} mW")

        # 3. Apply a mitigation strategy based on the calculated noise power.
        if mode == 'snr':
            # Strategy: Increase the target SNR margin to create more headroom against the noise.
            # Heuristic: Add 1 dB of margin for every 0.1 mW of total FEXT power.
            current_snr = self.hal.get_snr_margin()
            if current_snr is None:
                logging.error("Cannot apply SNR mitigation: failed to get current SNR.")
                return False

            snr_increase = int(total_fext_power_mw / 0.1)
            target_snr = current_snr + snr_increase

            logging.info(f"Mitigation: increasing SNR margin by {snr_increase} dB to a target of {target_snr:.1f} dB.")
            return self.hal.set_snr_margin(int(target_snr * 10))

        elif mode == 'power':
            # Strategy: Boost upstream power to "shout over" the noise.
            # Heuristic: Increase power by 1 dB for every 0.2 mW of total FEXT power.
            power_boost = int(total_fext_power_mw / 0.2)
            logging.info(f"Mitigation: applying upstream power boost of {power_boost} dB.")
            return self.hal.set_upstream_power_boost(power_boost)

        else:
            logging.error(f"Unknown mitigation mode: {mode}. Supported modes are 'snr' and 'power'.")
            return False

    def force_dynamic_reconfiguration(self) -> bool:
        """
        Triggers a dynamic reconfiguration event (DRA) on the line.

        This is typically a 'fast retrain' that adjusts parameters without
        dropping the link entirely.

        Returns:
            True if the renegotiation was triggered successfully, False otherwise.
        """
        logging.info("Forcing dynamic line reconfiguration (DRA)...")
        try:
            success = self.hal.force_renegotiation()
            if success:
                logging.info("Successfully triggered dynamic reconfiguration.")
            else:
                logging.error("HAL failed to trigger dynamic reconfiguration.")
            return success
        except NotImplementedError:
            logging.error(f"Dynamic reconfiguration is not supported by the {self.hal.__class__.__name__} HAL.")
            return False

    def manipulate_sra(self, enable_bitswap: bool, target_snr_floor_db: float | None = None) -> dict:
        """
        Manipulates Seamless Rate Adaptation (SRA) behavior.

        It enables/disables bit-swap and can optionally trigger SNR reduction
        to encourage a rate change.

        Args:
            enable_bitswap: Whether to enable or disable the bit-swap feature.
            target_snr_floor_db: If provided, will dynamically reduce SNR to this
                                 floor to provoke SRA.

        Returns:
            A dictionary reporting the success of the operations.
        """
        logging.info(f"Manipulating SRA: Bit-swap enabled -> {enable_bitswap}")
        results = {}

        try:
            bitswap_success = self.hal.control_bitswap(enable_bitswap)
            results["bitswap_control_set"] = bitswap_success
            if not bitswap_success:
                logging.error("Failed to control bit-swap. Aborting SRA manipulation.")
                return results
        except NotImplementedError:
            logging.error(f"Bit-swap control is not supported by the {self.hal.__class__.__name__} HAL.")
            results["bitswap_control_set"] = False
            return results

        if target_snr_floor_db is not None:
            logging.info(f"Proceeding with SNR reduction to provoke SRA...")
            sra_results = self.dynamically_reduce_snr(target_snr_floor_db)
            results.update(sra_results)

        return results

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

    def control_tone_activation(self, tone_map: dict[int, bool]) -> bool:
        """
        Applies a complete activation map for DMT (Discrete Multi-Tone) tones.

        Args:
            tone_map: A dictionary mapping a tone index to a boolean (True=on, False=off).

        Returns:
            True if the tone activation map was successfully applied, False otherwise.
        """
        logging.info(f"Applying new tone activation map for {len(tone_map)} tones...")

        if not tone_map:
            logging.warning("Empty tone map provided for activation control.")
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
        Calculates and applies an optimal bit and tone allocation based on a
        physics model for a simulated line distance.

        Args:
            target_distance_m: The simulated line distance to optimize for.
            snr_threshold_db: The minimum SNR for a tone to be considered usable.

        Returns:
            True if the optimization was successfully applied, False otherwise.
        """
        logging.info(f"Optimizing tone allocation for a simulated distance of {target_distance_m}m...")

        # 1. Calculate the SNR profile and get corresponding tone indices.
        snr_per_tone = self.physics.calculate_snr_per_tone(distance_m=target_distance_m)
        all_tones = self.physics.get_tone_indices()

        if len(snr_per_tone) != len(all_tones):
            logging.error("Mismatch between SNR profile and tone indices. Aborting optimization.")
            return False

        # 2. Determine bit allocation and a complete tone activation map.
        bit_allocation = {}
        tone_activation_map = {tone: True for tone in all_tones} # Start with all tones active

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
            tone_index = all_tones[i]
            if snr < snr_threshold_db:
                # If SNR is too low, deactivate the tone and assign 0 bits.
                tone_activation_map[tone_index] = False
                bit_allocation[tone_index] = 0
            else:
                # Otherwise, assign the calculated number of bits.
                bit_allocation[tone_index] = final_bits_per_tone[i]

        logging.info(f"Optimization plan: Deactivating {len([t for t, a in tone_activation_map.items() if not a])} tones.")

        # 3. Apply the new configuration via the HAL.
        success_activation = self.control_tone_activation(tone_activation_map)

        if not success_activation:
            logging.error("Failed to apply tone activation map. Aborting further optimization.")
            return False

        logging.info("Applying optimized bit-loading table...")
        success_bitload = self.set_per_tone_bit_loading(bit_allocation)

        if success_bitload:
            logging.info("Successfully applied full tone allocation optimization.")
        else:
            logging.error("Failed to apply tone allocation optimization.")

        return success_bitload

    def run_persistent_showtime_optimization(
        self,
        target_distance_m: int,
        monitoring_duration_s: int = 600,
        check_interval_s: int = 30,
        crc_error_threshold: int = 100
    ) -> dict:
        """
        Runs a loop to maintain an optimized line state over time.

        It periodically checks for line degradation (via CRC errors) and
        re-applies the full, calculated optimal profile if necessary.

        Args:
            target_distance_m: The target distance for optimization calculations.
            monitoring_duration_s: Total time to run the optimization loop.
            check_interval_s: How often to check line stats.
            crc_error_threshold: New CRC errors per interval that trigger re-optimization.

        Returns:
            A dictionary summarizing the results of the persistent optimization.
        """
        logging.info(f"Starting persistent showtime optimization for {monitoring_duration_s}s...")
        start_time = time.time()
        end_time = start_time + monitoring_duration_s
        reoptimizations_triggered = 0

        # Apply the initial optimal profile
        logging.info("Applying initial optimal profile...")
        initial_success = self.optimize_tone_allocation(target_distance_m)
        if not initial_success:
            logging.error("Failed to apply initial optimal profile. Aborting.")
            return {"success": False, "reoptimizations": 0}

        # Get baseline stats after initial optimization
        time.sleep(check_interval_s / 2) # Wait a moment for stats to update
        last_stats = self.hal.get_line_stats()
        last_crc_errors = last_stats.get('crc_errors', 0) if last_stats else 0
        logging.info(f"Initial CRC count: {last_crc_errors}. Monitoring for spikes.")

        while time.time() < end_time:
            time.sleep(check_interval_s)

            current_stats = self.hal.get_line_stats()
            if not current_stats:
                logging.warning("Could not retrieve line stats. Skipping check.")
                continue

            current_crc_errors = current_stats.get('crc_errors', 0)
            new_errors = current_crc_errors - last_crc_errors

            logging.info(f"Monitoring... New CRC errors in last {check_interval_s}s: {new_errors}")

            if new_errors > crc_error_threshold:
                logging.warning(f"CRC error threshold exceeded ({new_errors} > {crc_error_threshold}). Re-applying profile.")
                reoptimizations_triggered += 1

                # Re-apply the full optimization profile
                self.optimize_tone_allocation(target_distance_m)

                # Reset baseline after re-optimization
                time.sleep(check_interval_s / 2)
                last_stats = self.hal.get_line_stats()
                last_crc_errors = last_stats.get('crc_errors', 0) if last_stats else 0
                logging.info(f"Re-optimization complete. New CRC count: {last_crc_errors}")
            else:
                last_crc_errors = current_crc_errors

        logging.info(f"Persistent optimization finished. Total re-optimizations: {reoptimizations_triggered}.")
        return {"success": True, "reoptimizations": reoptimizations_triggered}

    def exploit_bonding(self, enable_bonding: bool, group_id: int, mode: str, line_ids: list[int], delay_ms: int) -> dict:
        """
        Orchestrates a bonding exploitation scenario.

        Args:
            enable_bonding: Whether to enable or disable bonding.
            group_id: The ID of the bonding group to configure.
            mode: The bonding mode ('atm' or 'ethernet').
            line_ids: A list of line IDs to include in the group.
            delay_ms: The differential delay compensation in milliseconds.

        Returns:
            A dictionary reporting the success of the operations.
        """
        if not self.bonding_exploiter:
            logging.error("Bonding exploiter is not initialized.")
            return {"success": False}

        logging.info("Starting bonding exploitation...")
        results = {}

        # 1. Enable or disable bonding
        bonding_state_success = self.bonding_exploiter.control_bonding(enable_bonding)
        results["bonding_state_set"] = bonding_state_success
        if not bonding_state_success:
            logging.error("Failed to set bonding state. Aborting exploitation.")
            return results

        if enable_bonding:
            # 2. Configure the bonding group
            config_success = self.bonding_exploiter.configure_bonding(group_id, mode, line_ids)
            results["bonding_group_configured"] = config_success
            if not config_success:
                logging.error("Failed to configure bonding group. Aborting exploitation.")
                return results

            # 3. Optimize packet reordering
            delay_success = self.bonding_exploiter.optimize_packet_reordering(delay_ms)
            results["differential_delay_set"] = delay_success

            # 4. Attempt to bypass single-ended detection
            bypass_success = self.bonding_exploiter.bypass_single_ended_detection()
            results["bypass_attempted"] = bypass_success

        logging.info(f"Bonding exploitation finished. Results: {results}")
        return results