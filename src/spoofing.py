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
        Initializes the manipulator, detects hardware, and sets up advanced physics models.

        Args:
            ssh_interface: An active EntwareSSHInterface instance.
            profile: The VDSL2 profile to use for physics calculations (e.g., '17a').
        """
        self.dsl_interface = KeeneticDSLInterface(ssh_interface)
        self.physics = AdvancedDSLPhysics(profile=profile)

        self.hardware_detected = self.dsl_interface.detect_hardware()
        if not self.hardware_detected:
            raise RuntimeError("Failed to detect Keenetic hardware. Cannot proceed.")

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
        Calculates and applies a new DSL profile using advanced physics models.

        Args:
            target_rate_mbps: The desired data rate in Mbps.
            target_distance_m: The simulated target distance in meters.

        Returns:
            A dictionary reporting the success of each parameter write operation.
        """
        if not self.hardware_detected:
            return {"error": "Hardware not detected", "snr_margin_set": False, "attenuation_set": False}

        print(f"Setting target profile for {self.hardware_detected}: {target_rate_mbps} Mbps at {target_distance_m}m")

        # 1. Calculate required parameters using the advanced physics model
        target_snr = self._find_optimal_snr_for_rate(target_rate_mbps, target_distance_m)
        attenuations = self.physics.model_frequency_dependent_attenuation(distance_m=target_distance_m)
        # For now, we take the average attenuation across bands as the target value.
        target_attenuation = np.mean(list(attenuations.values()))

        print(f"Calculated Targets -> Required SNR: {target_snr} dB, Avg Attenuation: {target_attenuation:.2f} dB")

        # 2. Write parameters to hardware registers
        results = {}

        # Write SNR margin if supported
        if 'snr_margin' in self.dsl_interface.hardware_specs.get('dsl_registers', {}):
            # The register value is often in 0.1 dB units
            snr_register_value = hex(int(target_snr * 10))
            results["snr_margin_set"] = self.dsl_interface.write_dsl_register(
                'snr_margin', snr_register_value
            )
        else:
            results["snr_margin_set"] = "not_supported"

        # Write attenuation if supported
        if 'attenuation' in self.dsl_interface.hardware_specs.get('dsl_registers', {}):
            attn_register_value = hex(int(target_attenuation * 10))
            results["attenuation_set"] = self.dsl_interface.write_dsl_register(
                'attenuation', attn_register_value
            )
        else:
            results["attenuation_set"] = "not_supported"

        print(f"Manipulation results: {results}")
        return results