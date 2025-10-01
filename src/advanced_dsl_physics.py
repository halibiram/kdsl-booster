import numpy as np
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- VDSL2 Profile and Physics Constants ---
# Based on ITU-T G.993.2 specifications and common physics models.

VDSL2_PROFILES = {
    '17a': {
        'frequency_bands': [(138e3, 3750e3), (5200e3, 8500e3), (12000e3, 17400e3)],
        'tone_spacing_hz': 4312.5,
        'total_tones': 4096,
        'psd_mask_dbm_hz': -40.0,  # Simplified flat PSD for this example
    },
    '35b': {
        'frequency_bands': [(138e3, 35328e3)],
        'tone_spacing_hz': 4312.5,
        'total_tones': 8192,
        'psd_mask_dbm_hz': -50.0, # Simplified flat PSD
    }
}

# Physical constants
FLAT_NOISE_FLOOR_DBM_HZ = -140.0  # Background thermal noise
TEMP_ATTENUATION_COEFFICIENT_DB_PER_C = 0.002 # Attenuation increase in dB per degree Celsius per meter

class AdvancedDSLPhysics:
    """
    Provides a more accurate physics-based model for VDSL2 parameter calculation,
    incorporating per-tone calculations and environmental factors.
    """
    SNR_GAP_DB = 12.8  # Represents implementation losses + target BER margin (more realistic than 9.8)
    MAX_BITS_PER_TONE = 15  # VDSL2 standard cap

    def __init__(self, profile='17a'):
        if profile not in VDSL2_PROFILES:
            raise ValueError(f"Profile '{profile}' not supported. Available: {list(VDSL2_PROFILES.keys())}")

        self.profile_data = VDSL2_PROFILES[profile]
        self.tone_spacing = self.profile_data['tone_spacing_hz']
        self.tones = self._generate_tones()
        logging.info(f"Initialized physics model for VDSL2 profile {profile} with {len(self.tones)} active tones.")

    def _generate_tones(self) -> np.ndarray:
        """Generates an array of frequencies for each active tone in the profile."""
        active_tones = []
        for start_freq, end_freq in self.profile_data['frequency_bands']:
            start_tone_index = int(start_freq / self.tone_spacing)
            end_tone_index = int(end_freq / self.tone_spacing)
            for i in range(start_tone_index, end_tone_index + 1):
                active_tones.append(i * self.tone_spacing)
        return np.array(active_tones)

    def get_tone_indices(self) -> np.ndarray:
        """Generates an array of indices for each active tone in the profile."""
        active_tone_indices = []
        for start_freq, end_freq in self.profile_data['frequency_bands']:
            start_tone_index = int(start_freq / self.tone_spacing)
            end_tone_index = int(end_freq / self.tone_spacing)
            for i in range(start_tone_index, end_tone_index + 1):
                active_tone_indices.append(i)
        return np.array(active_tone_indices)

    def model_attenuation_per_tone(self, distance_m: int, temperature_c: float = 20.0) -> np.ndarray:
        """
        Models attenuation for each tone based on frequency, distance, and temperature.
        Uses the standard K-L model for twisted pair cables: Att(f) = k * sqrt(f).

        Args:
            distance_m: The line distance in meters.
            temperature_c: The ambient temperature in Celsius.

        Returns:
            A numpy array of attenuation values in dB for each active tone.
        """
        # Cable loss constant (k) for typical 0.5mm (24 AWG) copper wire.
        # This value is tuned to produce realistic attenuation profiles (e.g. ~40-60dB at 1km for high freqs).
        k_cable_loss = 6.0e-2

        attenuation_db_per_km = k_cable_loss * np.sqrt(self.tones)
        base_attenuation = (attenuation_db_per_km / 1000) * distance_m

        # Add temperature effect
        temp_factor = 1 + (TEMP_ATTENUATION_COEFFICIENT_DB_PER_C * (temperature_c - 20))

        return base_attenuation * temp_factor

    def calculate_snr_per_tone(self, distance_m: int, temperature_c: float = 20.0) -> np.ndarray:
        """
        Calculates the Signal-to-Noise Ratio (SNR) for each individual tone.

        Args:
            distance_m: Line distance in meters.
            temperature_c: Ambient temperature in Celsius.

        Returns:
            A numpy array of SNR values in dB for each active tone.
        """
        # 1. Get transmit power per tone
        tx_power_dbm_per_tone = self.profile_data['psd_mask_dbm_hz'] + 10 * np.log10(self.tone_spacing)

        # 2. Calculate attenuation for each tone
        attenuation_db = self.model_attenuation_per_tone(distance_m, temperature_c)

        # 3. Calculate received power for each tone
        rx_power_dbm_per_tone = tx_power_dbm_per_tone - attenuation_db

        # 4. Calculate noise power in each tone's bandwidth
        noise_power_dbm_per_tone = FLAT_NOISE_FLOOR_DBM_HZ + 10 * np.log10(self.tone_spacing)

        # 5. Calculate SNR for each tone
        snr_db = rx_power_dbm_per_tone - noise_power_dbm_per_tone
        return snr_db

    def calculate_max_bitrate(self, distance_m: int, temperature_c: float = 20.0) -> float:
        """
        Calculates the maximum achievable data rate by summing the capacity of each tone.
        This uses a bit-loading algorithm based on the Shannon-Hartley theorem.

        Args:
            distance_m: The line distance in meters.
            temperature_c: The ambient temperature in Celsius.

        Returns:
            The maximum theoretical data rate in Mbps.
        """
        snr_per_tone_db = self.calculate_snr_per_tone(distance_m, temperature_c)

        # Convert SNR from dB to a linear ratio and adjust for the SNR gap
        snr_gap_linear = 10 ** (self.SNR_GAP_DB / 10)
        effective_snr_linear = (10 ** (snr_per_tone_db / 10)) / snr_gap_linear

        # Calculate bits per tone (log base 2)
        # We use a mask to avoid log2(negative) for tones with SNR < 0
        bits_per_tone = np.zeros_like(effective_snr_linear)
        positive_snr_mask = effective_snr_linear > 0
        bits_per_tone[positive_snr_mask] = np.log2(1 + effective_snr_linear[positive_snr_mask])

        # Apply the maximum bits per tone cap
        bits_per_tone = np.clip(bits_per_tone, 0, self.MAX_BITS_PER_TONE)

        # Total bitrate is the sum of bits per tone times the tone spacing (symbol rate)
        total_bitrate_bps = np.sum(bits_per_tone) * self.tone_spacing

        return round(total_bitrate_bps / 1_000_000, 2) # Convert to Mbps

    def get_safe_power_boost_limit(self, current_attenuation: float, regulatory_limit_dbm: float = 20.0) -> float:
        """
        Calculates the maximum safe power boost based on line conditions.

        Args:
            current_attenuation: The current measured line attenuation.
            regulatory_limit_dbm: The regulatory power limit in dBm.

        Returns:
            The maximum safe power boost in dB.
        """
        # This is a placeholder for a more complex calculation.
        # A real implementation would consider frequency-dependent limits.
        logging.info(f"Calculating safe power boost limit for attenuation {current_attenuation} dB...")
        if current_attenuation > 40:
            # High attenuation, allow more boost
            return 5.0
        elif current_attenuation > 20:
            # Medium attenuation, allow moderate boost
            return 3.0
        else:
            # Low attenuation, be conservative
            return 1.0

    def generate_optimal_psd_shape(self, target_rate_mbps: float, distance_m: int) -> dict:
        """
        Generates an optimal per-band PSD configuration.

        Args:
            target_rate_mbps: The desired data rate.
            distance_m: The line distance in meters.

        Returns:
            A dictionary with the optimal per-band PSD configuration.
        """
        # This is a placeholder for a complex optimization algorithm.
        logging.info(f"Generating optimal PSD shape for {target_rate_mbps} Mbps at {distance_m}m...")
        if distance_m < 500:
            # Shorter loop, can use higher frequencies
            return {1: -40, 2: -45, 3: -50} # Example values
        else:
            # Longer loop, focus power on lower frequencies
            return {1: -35, 2: -50, 3: -60} # Example values