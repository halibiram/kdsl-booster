import numpy as np
import logging
from src.noise_models import ImpulseNoise, SHINE, AMRadioInterference, REIN

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

# --- Standard Cable Models (RLCG Parameters) ---
# Parameters are defined per meter, converted from standard per-km values.
CABLE_MODELS = {
    'etsi_05mm': {
        # Source: ITU-T G.996.1 (ex G.plt) Appendix A - 0.5mm (24 AWG)
        'R0': 173.0 / 1000.0,            # R(f) = R0 + R_skin*sqrt(f), R0 in Ohm/m
        'R_skin_coeff': 0.0442 / 1000.0, # Skin effect coefficient for f in Hz
        'L': 0.51e-3 / 1000.0,           # Inductance H/m (0.51 mH/km)
        'G_coeff': 2.5e-14,              # G(f) = G_coeff * f, G_coeff in S/(m*Hz)
        'C': 51e-9 / 1000.0,             # Capacitance F/m (51 nF/km)
        'description': 'Standard 0.5mm (24 AWG) cable as per ETSI/ITU specs.'
    },
    'ansi_26awg': {
        # Typical values for 26 AWG cable.
        'R0': 275.0 / 1000.0,
        'R_skin_coeff': 0.055 / 1000.0,
        'L': 0.5e-3 / 1000.0,
        'G_coeff': 2.0e-14,
        'C': 50e-9 / 1000.0,
        'description': 'Standard 26 AWG cable as per ANSI specs.'
    }
}

class AdvancedDSLPhysics:
    """
    Provides a more accurate physics-based model for VDSL2 parameter calculation,
    incorporating per-tone calculations and environmental factors.
    Now uses an RLCG-based model for channel characteristics.
    """
    SNR_GAP_DB = 12.8  # Represents implementation losses + target BER margin (more realistic than 9.8)
    MAX_BITS_PER_TONE = 15  # VDSL2 standard cap

    def __init__(self, profile='17a', cable_model='etsi_05mm', noise_models: dict = None):
        if profile not in VDSL2_PROFILES:
            raise ValueError(f"Profile '{profile}' not supported. Available: {list(VDSL2_PROFILES.keys())}")
        if cable_model not in CABLE_MODELS:
            raise ValueError(f"Cable model '{cable_model}' not supported. Available: {list(CABLE_MODELS.keys())}")

        self.profile_data = VDSL2_PROFILES[profile]
        self.tone_spacing = self.profile_data['tone_spacing_hz']
        self.tones = self._generate_tones()
        self.cable_params = CABLE_MODELS[cable_model]
        self.noise_models = noise_models if noise_models else {}
        # Initial background noise is the flat thermal noise floor
        self.background_noise_psd_dbm_hz = np.full_like(self.tones, FLAT_NOISE_FLOOR_DBM_HZ)

        logging.info(f"Initialized physics model for VDSL2 profile {profile} using '{cable_model}' cable model.")
        if self.noise_models:
            logging.info(f"Noise models loaded: {list(self.noise_models.keys())}")

    def _generate_tones(self) -> np.ndarray:
        """Generates an array of frequencies for each active tone in the profile."""
        active_tones = []
        for start_freq, end_freq in self.profile_data['frequency_bands']:
            start_tone_index = int(start_freq / self.tone_spacing)
            end_tone_index = int(end_freq / self.tone_spacing)
            for i in range(start_tone_index, end_tone_index + 1):
                # Avoid f=0 which causes issues in calculations
                freq = i * self.tone_spacing
                if freq == 0: continue
                active_tones.append(freq)
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

    def _calculate_propagation_constant(self):
        """
        Calculates the complex propagation constant (gamma) based on the RLCG model.
        gamma = sqrt((R + j*omega*L) * (G + j*omega*C))
        """
        omega = 2 * np.pi * self.tones

        # R(f) in Ohm/m, using per-meter parameters from the selected cable model
        R = self.cable_params['R0'] + self.cable_params['R_skin_coeff'] * np.sqrt(self.tones)
        L = self.cable_params['L']  # H/m
        C = self.cable_params['C']  # F/m
        # G(f) = g_coeff * f, a more realistic model for dielectric loss
        G = self.cable_params['G_coeff'] * self.tones # S/m

        # Complex impedance (per meter) and admittance (per meter)
        Z = R + 1j * omega * L
        Y = G + 1j * omega * C

        gamma = np.sqrt(Z * Y)
        return gamma

    def model_attenuation_per_tone(self, distance_m: int, temperature_c: float = 20.0) -> np.ndarray:
        """
        Models attenuation for each tone based on the RLCG model.
        Attenuation (dB) = 20 * log10(e) * real(gamma) * distance_km

        Args:
            distance_m: The line distance in meters.
            temperature_c: The ambient temperature in Celsius.

        Returns:
            A numpy array of attenuation values in dB for each active tone.
        """
        gamma = self._calculate_propagation_constant()

        # Attenuation constant (alpha) is the real part of gamma
        alpha = np.real(gamma)

        # Attenuation in dB per meter
        attenuation_db_per_m = alpha * 8.686 # 20 * log10(e)

        base_attenuation = attenuation_db_per_m * distance_m

        # Add temperature effect (simple model, affects resistance mainly)
        temp_factor = 1 + (TEMP_ATTENUATION_COEFFICIENT_DB_PER_C * (temperature_c - 20))

        return base_attenuation * temp_factor

    def model_fext_noise_psd(self, n_disturbers: int, distance_m: int) -> np.ndarray:
        """
        Models the Far-End Crosstalk (FEXT) noise Power Spectral Density (PSD).
        Uses the "1% 49-disturber" model, scaled for the actual number of disturbers.
        FEXT_PSD = TX_PSD * |H_fext(f)|^2
        |H_fext(f)|^2 = k_fext * (d/d0) * |H_channel(f)|^2 * f^2

        Args:
            n_disturbers: The number of interfering DSL lines.
            distance_m: The line distance in meters.

        Returns:
            A numpy array of FEXT noise PSD in dBm/Hz for each active tone.
        """
        # FEXT coupling coefficient for 99% worst-case 49-pair binder group
        # This is an empirical value from standards.
        k_fext_49 = 8.8e-20

        # Scale the coupling constant for the actual number of disturbers
        k_fext = k_fext_49 * (n_disturbers / 49)**0.6

        # FEXT is proportional to the square of the frequency and the length
        f_squared = self.tones**2

        # Calculate channel transfer function squared |H(f)|^2 from attenuation
        attenuation_db = self.model_attenuation_per_tone(distance_m)
        h_squared = 10**(-attenuation_db / 10)

        # Calculate FEXT transfer function
        h_fext_squared = k_fext * distance_m * h_squared * f_squared

        # FEXT noise PSD is the transmit PSD shaped by the FEXT transfer function
        tx_psd_dbm_hz = self.profile_data['psd_mask_dbm_hz']
        # Add a small epsilon to prevent log10(0) which results in -inf
        fext_psd_dbm_hz = tx_psd_dbm_hz + 10 * np.log10(h_fext_squared + 1e-30)

        return fext_psd_dbm_hz

    def update_background_noise(self, new_noise_psd_dbm_hz: np.ndarray):
        """
        Updates the background noise profile of the simulation.
        This can be used to simulate changing line conditions.

        Args:
            new_noise_psd_dbm_hz (np.ndarray): The new background noise PSD in dBm/Hz.
                                               Must have the same shape as self.tones.
        """
        if new_noise_psd_dbm_hz.shape != self.tones.shape:
            raise ValueError("The new noise PSD must have the same shape as the tone array.")

        self.background_noise_psd_dbm_hz = new_noise_psd_dbm_hz
        logging.info("Background noise profile has been updated.")

    def calculate_snr_per_tone(self, distance_m: int, n_disturbers: int = 10, temperature_c: float = 20.0, duration_sec: float = 1.0) -> np.ndarray:
        """
        Calculates the Signal-to-Noise Ratio (SNR) for each individual tone,
        including the effects of FEXT crosstalk and other configured noise models.

        Args:
            distance_m: Line distance in meters.
            n_disturbers: The number of interfering lines in the cable bundle.
            temperature_c: Ambient temperature in Celsius.
            duration_sec: The duration over which to model time-variant noise (e.g., impulse).

        Returns:
            A numpy array of SNR values in dB for each active tone.
        """
        # 1. Get transmit power per tone and calculate received power
        tx_power_dbm_per_tone = self.profile_data['psd_mask_dbm_hz'] + 10 * np.log10(self.tone_spacing)
        attenuation_db = self.model_attenuation_per_tone(distance_m, temperature_c)
        rx_power_dbm_per_tone = tx_power_dbm_per_tone - attenuation_db

        # 2. Calculate baseline noise (background + FEXT)
        background_noise_power_mw = 10**(self.background_noise_psd_dbm_hz / 10) * self.tone_spacing

        fext_noise_psd_dbm_hz = self.model_fext_noise_psd(n_disturbers, distance_m)
        fext_noise_power_mw = 10**(fext_noise_psd_dbm_hz / 10) * self.tone_spacing

        total_noise_power_mw = background_noise_power_mw + fext_noise_power_mw

        # 3. Add noise from configured models
        for name, model in self.noise_models.items():
            logging.info(f"Applying noise model: {name}")
            noise_psd_dbm_hz = 0
            if isinstance(model, (ImpulseNoise, SHINE)):
                # Symbol rate is the same as tone spacing in VDSL2
                noise_psd_dbm_hz = model.generate_noise_psd(self.tones, self.tone_spacing, duration_sec)
            elif isinstance(model, (AMRadioInterference, REIN)):
                noise_psd_dbm_hz = model.generate_noise_psd(self.tones)
            else:
                logging.warning(f"Unknown noise model type for '{name}'. Skipping.")
                continue

            # Convert PSD to power and add to total
            additional_noise_power_mw = 10**(noise_psd_dbm_hz / 10) * self.tone_spacing
            total_noise_power_mw += additional_noise_power_mw

        # 4. Calculate final SNR
        rx_power_mw = 10**(rx_power_dbm_per_tone / 10)
        snr_linear = rx_power_mw / (total_noise_power_mw + 1e-20) # Add epsilon to avoid division by zero
        # Add a small epsilon to prevent log10(0) for tones with no signal
        snr_db = 10 * np.log10(snr_linear + 1e-30)

        return snr_db

    def calculate_max_bitrate(self, distance_m: int, n_disturbers: int = 10, temperature_c: float = 20.0, duration_sec: float = 1.0) -> float:
        """
        Calculates the maximum achievable data rate by summing the capacity of each tone.
        This uses a bit-loading algorithm based on the Shannon-Hartley theorem.

        Args:
            distance_m: The line distance in meters.
            n_disturbers: The number of interfering lines in the cable bundle.
            temperature_c: The ambient temperature in Celsius.
            duration_sec: The duration over which to model time-variant noise.

        Returns:
            The maximum theoretical data rate in Mbps.
        """
        snr_per_tone_db = self.calculate_snr_per_tone(distance_m, n_disturbers, temperature_c, duration_sec)

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