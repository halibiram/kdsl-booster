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
        Performs dependency analysis, conflict detection, and generates
        optimization recommendations.
        """
        warnings = []
        recommendations = []

        profiles_data = self.capabilities.get("vdsl2_profiles", {})
        freq_data = self.capabilities.get("frequency", {})
        vectoring_data = self.capabilities.get("vectoring", {})
        bonding_data = self.capabilities.get("bonding", {})
        retx_data = self.capabilities.get("retransmission", {})

        # --- Dependency and Conflict Analysis ---
        supported_profiles = profiles_data.get("consolidated_profiles", [])
        max_freq_mhz = freq_data.get("max_downstream_mhz", 0.0)

        high_speed_profiles = {"17a", "30a", "35b"}
        is_on_high_speed_profile = any(p in supported_profiles for p in high_speed_profiles)

        if "35b" in supported_profiles and max_freq_mhz < 30:
            warnings.append(f"Inconsistency: Profile 35b supported but max frequency is only {max_freq_mhz} MHz (requires >30 MHz).")
        if "30a" in supported_profiles and max_freq_mhz < 30:
            warnings.append(f"Inconsistency: Profile 30a supported but max frequency is only {max_freq_mhz} MHz (requires 30 MHz).")

        if vectoring_data.get("hardware_support") and not vectoring_data.get("is_active"):
            if is_on_high_speed_profile:
                warnings.append("Suboptimal Configuration: Vectoring is supported but not active, which will significantly limit performance on high-speed profiles (17a+).")
            else:
                recommendations.append("Enable Vectoring (G.993.5) to improve performance by reducing crosstalk.")

        if bonding_data.get("supported_standards") and not bonding_data.get("is_active"):
            warnings.append("Ambiguous State: Bonding is reported as supported by hardware (G.hs) but is not active. This may indicate a licensing or provisioning issue.")
            recommendations.append("Verify bonding configuration and licensing on the DSLAM to enable it.")

        # --- General Optimization Recommendations ---
        if retx_data.get("g_inp_supported") and not retx_data.get("is_active"):
            recommendations.append("Enable G.inp (Retransmission) to improve line stability, especially in noisy environments.")

        return {
            "warnings": warnings,
            "recommendations": recommendations
        }