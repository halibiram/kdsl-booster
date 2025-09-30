"""
This module provides the DSLAMProfiler class, which is responsible for
analyzing the consolidated capability data to provide higher-level insights,
such as dependency analysis and optimization recommendations.
"""
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DSLAMProfiler:
    """
    Analyzes a complete capability profile to find inconsistencies and
    suggest optimizations.
    """

    def __init__(self, capability_data: dict):
        """
        Initializes the profiler with the consolidated capability data.
        """
        self.capabilities = capability_data if capability_data else {}

    def generate_profile_analysis(self) -> dict:
        """
        Performs dependency analysis and generates optimization recommendations.
        """
        warnings = []
        recommendations = []

        # --- Dependency Analysis ---
        profiles_data = self.capabilities.get("vdsl2_profiles", {})
        freq_data = self.capabilities.get("frequency", {})

        if profiles_data and freq_data:
            supported_profiles = profiles_data.get("consolidated_profiles", [])
            max_freq_mhz = freq_data.get("max_downstream_mhz", 0.0)

            if "35b" in supported_profiles and max_freq_mhz < 30:
                warnings.append(
                    f"Inconsistency Detected: Profile 35b is supported, but the maximum "
                    f"downstream frequency ({max_freq_mhz} MHz) is less than the required 35 MHz."
                )
            if "30a" in supported_profiles and max_freq_mhz < 30:
                warnings.append(
                    f"Inconsistency Detected: Profile 30a is supported, but the maximum "
                    f"downstream frequency ({max_freq_mhz} MHz) is less than the required 30 MHz."
                )

        # --- Optimization Recommendations ---
        vectoring_data = self.capabilities.get("vectoring", {})
        if vectoring_data.get("hardware_support") and not vectoring_data.get("is_active"):
            recommendations.append(
                "Enable Vectoring (G.993.5) to improve performance by reducing crosstalk."
            )

        retx_data = self.capabilities.get("retransmission", {})
        if retx_data.get("g_inp_supported") and not retx_data.get("is_active"):
            recommendations.append(
                "Enable G.inp (Retransmission) to improve line stability, especially in noisy environments."
            )

        bonding_data = self.capabilities.get("bonding", {})
        if bonding_data.get("supported_standards") and not bonding_data.get("is_active"):
            recommendations.append(
                "Enable Bonding to aggregate bandwidth across multiple pairs for higher speeds."
            )

        return {
            "warnings": warnings,
            "recommendations": recommendations
        }