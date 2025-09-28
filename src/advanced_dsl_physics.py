import numpy as np
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants based on VDSL2 specifications (ITU-T G.993.2) and general physics.
# These would be refined with real-world data.
VDSL2_TONE_SPACING_HZ = 4312.5  # Standard tone spacing for VDSL2
FLAT_NOISE_FLOOR_DBM_HZ = -140.0  # A common assumption for background noise in dBm/Hz
CODING_GAIN_DB = 3.0  # Assumed coding gain from FEC/trellis
SNR_GAP_DB = 9.8  # Theoretical gap to Shannon capacity limit in dB

class AdvancedDSLPhysics:
    """
    Provides more sophisticated, physics-based models for DSL parameter calculation,
    aligning with ITU-T G.993.2 standards for VDSL2.
    """

    def __init__(self, profile='17a'):
        """
        Initializes the physics model for a specific VDSL2 profile.

        Args:
            profile (str): The VDSL2 profile to model (e.g., '8b', '17a', '35b').
        """
        self.profile = profile
        self.downstream_bands = self._get_profile_bands(profile)
        self.tones_per_band = self._calculate_tones_per_band()
        logging.info(f"Initialized advanced physics model for VDSL2 profile {profile}")
        logging.info(f"Downstream bands (Hz): {self.downstream_bands}")

    def _get_profile_bands(self, profile):
        """Returns the downstream frequency bands for a given VDSL2 profile."""
        bands = {
            '17a': [(138000, 3750000), (5200000, 8500000), (12000000, 17400000)],
            '35b': [(138000, 35000000)] # Simplified for this example
        }
        return bands.get(profile, bands['17a'])

    def _calculate_tones_per_band(self):
        """Calculates the number of tones within each frequency band."""
        tones = {}
        for i, (start_freq, end_freq) in enumerate(self.downstream_bands):
            num_tones = int((end_freq - start_freq) / VDSL2_TONE_SPACING_HZ)
            tones[f'DS{i+1}'] = num_tones
        return tones

    def model_frequency_dependent_attenuation(self, distance_m: int) -> dict:
        """
        Models attenuation as a function of frequency and distance.
        This uses a simplified model (alpha * sqrt(f) + beta * f).

        Args:
            distance_m: The line distance in meters.

        Returns:
            A dictionary with average attenuation per band.
        """
        # More realistic coefficients for 0.5mm (24 AWG) copper cable.
        # These values produce more plausible attenuation figures (e.g., ~20-30 dB/km at 1 MHz).
        alpha = 2.2e-2  # Primary factor for frequency-dependent loss
        beta = 2.5e-8   # Secondary factor, more impactful at higher frequencies

        attenuations = {}
        for band_name, (start_freq, end_freq) in zip(self.tones_per_band.keys(), self.downstream_bands):
            # Calculate attenuation at the center frequency of the band
            center_freq = (start_freq + end_freq) / 2
            attenuation_db_per_km = (alpha * np.sqrt(center_freq)) + (beta * center_freq)
            total_attenuation = (attenuation_db_per_km / 1000) * distance_m
            attenuations[band_name] = round(total_attenuation, 2)

        logging.info(f"Modeled attenuations for {distance_m}m: {attenuations}")
        return attenuations

    def calculate_max_bitrate(self, target_snr_db: float, distance_m: int) -> float:
        """
        Calculates the maximum achievable data rate using the Shannon-Hartley theorem,
        summed across all tones in the profile.

        Args:
            target_snr_db: The target average Signal-to-Noise Ratio in dB.
            distance_m: The line distance in meters, used for attenuation modeling.

        Returns:
            The maximum theoretical data rate in Mbps.
        """
        total_bitrate_bps = 0
        attenuations = self.model_frequency_dependent_attenuation(distance_m)

        # Effective SNR after accounting for coding gain and Shannon gap
        effective_snr_db = target_snr_db + CODING_GAIN_DB - SNR_GAP_DB

        if effective_snr_db <= 0:
            return 0.0

        for band_name, num_tones in self.tones_per_band.items():
            # Apply the band-specific attenuation to the SNR
            band_attenuation = attenuations.get(band_name, 0)
            snr_after_attenuation = effective_snr_db - band_attenuation

            if snr_after_attenuation <= 0:
                continue

            # Convert dB to a linear power ratio
            snr_linear = 10 ** (snr_after_attenuation / 10)

            # Shannon-Hartley for a single tone
            bits_per_tone = np.log2(1 + snr_linear)

            # Max bits per tone is capped in DSL (e.g., 15 bits)
            bits_per_tone = min(bits_per_tone, 15.0)

            # Bitrate for this band
            band_bitrate = num_tones * bits_per_tone * VDSL2_TONE_SPACING_HZ
            total_bitrate_bps += band_bitrate

        return round(total_bitrate_bps / 1_000_000, 2) # Convert to Mbps