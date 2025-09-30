"""
This module contains the core logic for DSL parameter spoofing.

It includes physics-based models for calculating realistic target values for
parameters like attenuation and SNR. It also provides the high-level classes
that orchestrate the manipulation of kernel parameters to achieve the desired
line performance.
"""
import numpy as np

from src.entware_ssh import EntwareSSHInterface
from src.keenetic_dsl_interface import KeeneticDSLInterface
from src.advanced_dsl_physics import AdvancedDSLPhysics


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

        # 2. Write SNR margin to the hardware via the HAL
        success = self.hal.set_snr_margin(snr_register_value)

        results = {
            "snr_margin_set": success,
            "attenuation_set": "not_supported",
            "applied_snr_db": target_snr if success else 0,
            "applied_attenuation_db": target_attenuation,
        }

        print(f"Manipulation results: {results}")
        return results