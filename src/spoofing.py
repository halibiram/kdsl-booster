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
    Calculates a realistic target attenuation value based on a simulated distance.

    This uses a simplified linear model. A real-world implementation would
    generate a complex attenuation profile across all VDSL2 tones.

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
    Calculates the required Signal-to-Noise Ratio (SNR) to achieve a target data rate.

    This model is based on the Shannon-Hartley theorem, which implies a logarithmic
    relationship between data rate and SNR. A common rule of thumb is that
    doubling the data rate requires a 6 dB increase in SNR.
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
from src.kernel_dsl_access import write_kernel_parameter


class KernelDSLManipulator:
    """
    Orchestrates the manipulation of DSL kernel parameters.

    This class uses the physics-based models to calculate target values and
    then uses the kernel_dsl_access functions to write these values to the
    live system, effectively spoofing the line parameters.
    """

    def __init__(
        self,
        ssh_interface: EntwareSSHInterface,
        base_rate_mbps: float,
        base_snr_db: float,
    ):
        """
        Initializes the manipulator with an active SSH interface and baseline metrics.

        Args:
            ssh_interface: An active EntwareSSHInterface instance.
            base_rate_mbps: The current, measured data rate in Mbps.
            base_snr_db: The current, measured SNR in dB.
        """
        self.ssh_interface = ssh_interface
        self.snr_spoofer = DynamicSNRSpoofer(base_rate_mbps, base_snr_db)

        # Hypothetical paths for kernel parameters. In a real scenario, these
        # would be discovered or configured based on the target device.
        self.PARAM_PATHS = {
            "snr_margin": "/sys/module/dsl/parameters/snr_margin_override",
            "attenuation": "/sys/module/dsl/parameters/attenuation_override",
        }

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
        print(f"Setting target profile: {target_rate_mbps} Mbps at {target_distance_m}m")

        # 1. Calculate target parameters from models
        target_snr = self.snr_spoofer.calculate_optimal_snr_curve(target_rate_mbps)
        target_attenuation = calculate_realistic_attenuation(target_distance_m)

        print(f"Calculated Targets -> SNR: {target_snr} dB, Attenuation: {target_attenuation} dB")

        # 2. Write parameters to the kernel via SSH
        results = {}

        # Write SNR margin
        snr_path = self.PARAM_PATHS["snr_margin"]
        results["snr_margin_set"] = write_kernel_parameter(
            self.ssh_interface, snr_path, str(target_snr)
        )

        # Write attenuation
        attenuation_path = self.PARAM_PATHS["attenuation"]
        results["attenuation_set"] = write_kernel_parameter(
            self.ssh_interface, attenuation_path, str(target_attenuation)
        )

        print(f"Manipulation results: {results}")
        return results