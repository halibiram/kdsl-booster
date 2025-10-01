import logging
from src.keenetic_dsl_interface import DslHalBase
from src.advanced_dsl_physics import AdvancedDSLPhysics, FLAT_NOISE_FLOOR_DBM_HZ

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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

        analysis = {
            "status": "completed",
            "average_noise_dbm_hz": sum(qln_data.values()) / len(qln_data) if qln_data else 0,
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