"""
This module contains the core logic for DSL parameter spoofing.

It includes physics-based models for calculating realistic target values for
parameters like attenuation and SNR. It also provides the high-level classes
that orchestrate the manipulation of kernel parameters to achieve the desired
line performance.
"""
import numpy as np

# A simplified linear model for VDSL2 attenuation.
# Based on the observation that 300m corresponds to ~18.5 dB in the spec.
# This yields a loss factor of roughly 0.0617 dB/meter.
# A more complex model would account for frequency-dependent loss across different tones.
ATTENUATION_PER_METER_DB = 18.5 / 300

def calculate_realistic_attenuation(target_distance_m: int) -> float:
    """
    Calculates a realistic target attenuation based on a simulated line distance.

    This function uses a simplified linear model where attenuation is directly
    proportional to distance. The model is calibrated based on the project
    specification's reference value (18.5 dB at 300m). A more advanced
    implementation would generate a complex, per-tone attenuation profile.

    Args:
        target_distance_m: The simulated target distance from the DSLAM in meters.

    Returns:
        The calculated target attenuation in dB, rounded to one decimal place.
    """
    if target_distance_m <= 0:
        # Return a minimal, non-zero attenuation for extremely short distances
        return 0.5

    calculated_attenuation = target_distance_m * ATTENUATION_PER_METER_DB

    return round(calculated_attenuation, 1)


class DynamicSNRSpoofer:
    """
    Calculates the required SNR to achieve a target data rate based on a baseline.

    This model uses the common rule of thumb for DSL performance, which is derived
    from the Shannon-Hartley theorem: doubling the data rate requires approximately
    a 6 dB increase in the Signal-to-Noise Ratio. This class encapsulates that
    logarithmic relationship.
    """
    def __init__(self, base_rate_mbps: float, base_snr_db: float):
        """
        Initializes the spoofer with a known baseline performance.

        Args:
            base_rate_mbps: The current, measured data rate in Mbps.
            base_snr_db: The current, measured SNR in dB.
        """
        self.base_rate_mbps = base_rate_mbps
        self.base_snr_db = base_snr_db
        # According to the "6dB per double" rule, the relationship is logarithmic.
        # Rate = k * log2(SNR_linear) => SNR_linear = 2^(Rate/k)
        # In dB, this means Rate is proportional to SNR_dB.
        # Rate2 / Rate1 = (SNR2_dB / SNR1_dB) is not quite right.
        # The doubling rule is an approximation: Rate2 = Rate1 * 2^((SNR2 - SNR1)/6)
        # So, (SNR2 - SNR1)/6 = log2(Rate2/Rate1)
        # SNR2 = SNR1 + 6 * log2(Rate2/Rate1)
        self.LOG2_FACTOR = 6.0

    def calculate_optimal_snr_curve(self, target_rate_mbps: float) -> float:
        """
        Calculates the target SNR required to achieve the desired data rate.

        Args:
            target_rate_mbps: The desired data rate in Mbps.

        Returns:
            The calculated target SNR in dB.
        """
        if target_rate_mbps <= self.base_rate_mbps:
            return self.base_snr_db

        rate_ratio = target_rate_mbps / self.base_rate_mbps

        # Calculate the required SNR boost in dB
        snr_boost_db = self.LOG2_FACTOR * np.log2(rate_ratio)

        target_snr_db = self.base_snr_db + snr_boost_db

        return round(target_snr_db, 1)


from src.entware_ssh import EntwareSSHInterface
from src.keenetic_dsl_interface import KeeneticDSLInterface


class KernelDSLManipulator:
    """
    Orchestrates the end-to-end process of calculating and applying spoofed parameters.

    This class acts as the main engine for the spoofing process. It uses the
    physics-based models to determine ideal kernel parameters and the hardware-aware
    KeeneticDSLInterface to write these values to the correct hardware registers.
    """

    def __init__(
        self,
        ssh_interface: EntwareSSHInterface,
        base_rate_mbps: float,
        base_snr_db: float,
    ):
        """
        Initializes the manipulator, detects hardware, and sets up spoofing models.

        Args:
            ssh_interface: An active EntwareSSHInterface instance.
            base_rate_mbps: The current, measured data rate in Mbps.
            base_snr_db: The current, measured SNR in dB.
        """
        self.dsl_interface = KeeneticDSLInterface(ssh_interface)
        self.snr_spoofer = DynamicSNRSpoofer(base_rate_mbps, base_snr_db)

        # Detect hardware on initialization to ensure the interface is ready
        self.hardware_detected = self.dsl_interface.detect_hardware()
        if not self.hardware_detected:
            # This is a critical failure; the manipulator cannot function
            # without knowing the hardware.
            raise RuntimeError("Failed to detect Keenetic hardware. Cannot proceed.")

    def set_target_profile(
        self, target_rate_mbps: float, target_distance_m: int
    ) -> dict:
        """
        Calculates and applies a new DSL profile based on target rate and distance.

        Args:
            target_rate_mbps: The desired data rate in Mbps.
            target_distance_m: The simulated target distance in meters.

        Returns:
            A dictionary reporting the success of each parameter write operation.
        """
        if not self.hardware_detected:
            print("Cannot set target profile: hardware not detected.")
            return {"error": "Hardware not detected", "snr_margin_set": False, "attenuation_set": False}

        print(f"Setting target profile for {self.hardware_detected}: {target_rate_mbps} Mbps at {target_distance_m}m")

        # 1. Calculate target parameters from models
        target_snr = self.snr_spoofer.calculate_optimal_snr_curve(target_rate_mbps)
        target_attenuation = calculate_realistic_attenuation(target_distance_m)

        print(f"Calculated Targets -> SNR: {target_snr} dB, Attenuation: {target_attenuation} dB")

        # 2. Convert to register format (e.g., 0.1 dB units, then hex) and write
        results = {}

        # Convert SNR to 0.1 dB units, then to a hex string for the register
        # Note: Some registers might not exist on all hardware (e.g., attenuation on Viva)
        if 'snr_margin' in self.dsl_interface.hardware_specs.get('dsl_registers', {}):
            snr_register_value = hex(int(target_snr * 10))
            results["snr_margin_set"] = self.dsl_interface.write_dsl_register(
                'snr_margin', snr_register_value
            )
        else:
            results["snr_margin_set"] = "not_supported"

        if 'attenuation' in self.dsl_interface.hardware_specs.get('dsl_registers', {}):
            attn_register_value = hex(int(target_attenuation * 10))
            results["attenuation_set"] = self.dsl_interface.write_dsl_register(
                'attenuation', attn_register_value
            )
        else:
            results["attenuation_set"] = "not_supported"

        print(f"Manipulation results: {results}")
        return results