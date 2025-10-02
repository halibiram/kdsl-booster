import logging
import numpy as np
from scipy.signal import find_peaks
from src.keenetic_dsl_interface import DslHalBase
from src.advanced_dsl_physics import AdvancedDSLPhysics, FLAT_NOISE_FLOOR_DBM_HZ

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants for diagnostic analysis
SPEED_OF_LIGHT = 299792458  # meters per second
VELOCITY_FACTOR = 0.66  # Typical velocity of propagation in copper pairs
LOADING_COIL_CUTOFF_FREQ_HZ = 80000 # Loading coils sharply cut off frequencies above ~80kHz
LOADING_COIL_ATTENUATION_THRESHOLD_DB = 20 # Attenuation at cutoff freq to be considered a coil
BRIDGED_TAP_MIN_PROMINENCE = 3 # Min dB prominence to consider a null a real bridged tap signature

class LineDiagnostics:
    """
    Provides a suite of tools for running DSL line diagnostics.
    """
    def __init__(self, hal: DslHalBase, profile: str = '17a'):
        """
        Initializes the LineDiagnostics class.

        Args:
            hal: An instance of a DSL Hardware Abstraction Layer (HAL).
            profile: The VDSL2 profile to use for physics calculations.
        """
        self.hal = hal
        self.physics = AdvancedDSLPhysics(profile=profile)
        logging.info(f"Line Diagnostics initialized for profile {profile}.")

    def run_selt(self) -> dict:
        """
        Runs a Single-Ended Line Test (SELT) and returns the results.
        """
        logging.info("Requesting SELT from HAL...")
        results = self.hal.run_selt()
        logging.info(f"SELT results received: {results}")
        return results

    def run_melt(self) -> dict:
        """
        Runs a Metallic Line Test (MELT) and returns the results.
        """
        logging.info("Requesting MELT from HAL...")
        results = self.hal.run_melt()
        logging.info(f"MELT results received: {results}")
        return results

    def run_delt(self) -> dict:
        """
        Runs a Dual-Ended Line Test (DELT) and returns the results.
        """
        logging.info("Requesting DELT from HAL...")
        results = self.hal.run_delt()
        logging.info(f"DELT results received: {results}")
        return results

    def analyze_qln(self, noise_margin_db: float = 6.0) -> dict:
        """
        Analyzes Quiet Line Noise (QLN) data from the HAL.

        Args:
            noise_margin_db: The threshold above the theoretical noise floor to flag as anomalous.

        Returns:
            A dictionary containing the QLN analysis.
        """
        logging.info("Requesting QLN data from HAL...")
        qln_data = self.hal.get_qln_data()

        if qln_data is None:
            logging.error("Failed to retrieve QLN data from HAL.")
            return {"status": "error", "message": "Could not get QLN data."}

        anomalous_tones = {}
        for tone, noise_level in qln_data.items():
            if noise_level > (FLAT_NOISE_FLOOR_DBM_HZ + noise_margin_db):
                anomalous_tones[tone] = {
                    "measured_noise": noise_level,
                    "noise_floor": FLAT_NOISE_FLOOR_DBM_HZ,
                    "anomaly_db": noise_level - FLAT_NOISE_FLOOR_DBM_HZ,
                }

        average_noise = 0
        if qln_data:
            average_noise = sum(qln_data.values()) / len(qln_data)

        analysis = {
            "status": "completed",
            "average_noise_dbm_hz": average_noise,
            "anomalous_tones_found": len(anomalous_tones),
            "anomalous_tones": anomalous_tones,
            "raw_data": qln_data,
        }
        logging.info(f"QLN analysis complete. Found {len(anomalous_tones)} anomalous tones.")
        return analysis

    def analyze_hlog(self, estimated_distance_m: int = 300, deviation_threshold_db: float = 10.0) -> dict:
        """
        Analyzes Hlog (channel characteristics) data from the HAL.

        Args:
            estimated_distance_m: The estimated line length in meters for the theoretical model.
            deviation_threshold_db: The dB threshold to flag a deviation as significant.

        Returns:
            A dictionary containing the Hlog analysis.
        """
        logging.info("Requesting Hlog data from HAL...")
        hlog_data = self.hal.get_hlog_data()

        if hlog_data is None:
            logging.error("Failed to retrieve Hlog data from HAL.")
            return {"status": "error", "message": "Could not get Hlog data."}

        theoretical_attenuation = self.physics.model_attenuation_per_tone(distance_m=estimated_distance_m)
        tone_indices = self.physics.get_tone_indices()

        # Ensure we have a 1-to-1 mapping of tone index to theoretical attenuation
        theoretical_hlog = dict(zip(tone_indices, theoretical_attenuation))

        deviating_tones = {}
        for tone, measured_atten in hlog_data.items():
            if tone in theoretical_hlog:
                theoretical_atten = theoretical_hlog[tone]
                deviation = abs(measured_atten - theoretical_atten)
                if deviation > deviation_threshold_db:
                    deviating_tones[tone] = {
                        "measured_attenuation": measured_atten,
                        "theoretical_attenuation": theoretical_atten,
                        "deviation_db": deviation,
                    }

        analysis = {
            "status": "completed",
            "estimated_distance_m": estimated_distance_m,
            "deviating_tones_found": len(deviating_tones),
            "deviating_tones": deviating_tones,
            "raw_data": hlog_data,
        }
        logging.info(f"Hlog analysis complete. Found {len(deviating_tones)} deviating tones.")
        return analysis

    def detect_loading_coils(self) -> dict:
        """
        Detects the presence of loading coils by checking for a sharp Hlog cutoff.
        """
        logging.info("Checking for loading coils...")
        hlog_data = self.hal.get_hlog_data()
        if not hlog_data:
            return {"status": "error", "message": "Could not get Hlog data."}

        # Find the tone closest to the cutoff frequency
        cutoff_tone_index = int(LOADING_COIL_CUTOFF_FREQ_HZ / self.physics.tone_spacing)

        if cutoff_tone_index in hlog_data and hlog_data[cutoff_tone_index] > LOADING_COIL_ATTENUATION_THRESHOLD_DB:
            msg = f"High attenuation ({hlog_data[cutoff_tone_index]:.1f} dB) at tone {cutoff_tone_index} indicates a likely loading coil."
            logging.warning(msg)
            return {"status": "completed", "loading_coil_detected": True, "message": msg}
        else:
            msg = "No evidence of loading coils found."
            logging.info(msg)
            return {"status": "completed", "loading_coil_detected": False, "message": msg}

    def detect_bridged_taps(self) -> dict:
        """
        Detects bridged taps by looking for periodic nulls in the Hlog data.
        """
        logging.info("Checking for bridged taps...")
        hlog_data = self.hal.get_hlog_data()
        if not hlog_data:
            return {"status": "error", "message": "Could not get Hlog data."}

        # Convert Hlog to numpy arrays for analysis
        tones = np.array(sorted(hlog_data.keys()))
        hlog_values = np.array([hlog_data[t] for t in tones])
        frequencies = tones * self.physics.tone_spacing

        # Find peaks (which are nulls in the transfer function) in the Hlog data
        peaks, properties = find_peaks(hlog_values, prominence=BRIDGED_TAP_MIN_PROMINENCE, width=5)

        if len(peaks) < 2:
            msg = "Not enough significant nulls found to indicate a bridged tap."
            logging.info(msg)
            return {"status": "completed", "bridged_tap_detected": False, "message": msg}

        # Calculate the frequency spacing between the nulls
        peak_frequencies = frequencies[peaks]
        deltas = np.diff(peak_frequencies)
        avg_delta_f = np.mean(deltas)

        # Estimate tap length: L = v_p / (2 * delta_f)
        velocity_of_propagation = SPEED_OF_LIGHT * VELOCITY_FACTOR
        estimated_length_m = velocity_of_propagation / (2 * avg_delta_f)

        msg = f"Detected {len(peaks)} periodic nulls with avg spacing {avg_delta_f/1e3:.1f} kHz, suggesting a bridged tap of ~{estimated_length_m:.1f}m."
        logging.info(msg)

        return {
            "status": "completed",
            "bridged_tap_detected": True,
            "message": msg,
            "estimated_tap_length_m": round(estimated_length_m, 2),
            "null_count": len(peaks),
            "avg_null_spacing_hz": round(avg_delta_f, 2),
            "detected_null_frequencies_hz": peak_frequencies.tolist()
        }