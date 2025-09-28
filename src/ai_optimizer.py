"""
This module provides an AI-powered optimizer for DSL parameters.

It uses machine learning models trained on data from the ExperimentRunner
to predict the optimal parameters (e.g., SNR margin, attenuation) required
to achieve a target performance metric, such as data rate.
"""

import numpy as np
from sklearn.linear_model import LinearRegression
from src.advanced_dsl_physics import AdvancedDSLPhysics


class AIOptimizer:
    """
    Uses a simple machine learning model to predict optimal DSL parameters based on
    the advanced physics model.
    """

    def __init__(self, dsl_profile: str = '17a'):
        """
        Initializes the AIOptimizer with a regression model and a physics model instance.
        """
        self.model = LinearRegression()
        self.physics = AdvancedDSLPhysics(profile=dsl_profile)
        self._is_trained = False

    def _find_optimal_snr_for_rate(self, target_rate_mbps: float, distance_m: int) -> float:
        """
        Performs an iterative search to find the minimum SNR for a target rate.
        This is a helper function to generate accurate training labels.
        """
        low_snr, high_snr = 0.0, 60.0
        optimal_snr = high_snr

        for _ in range(10):  # Binary search for 10 iterations for good precision
            mid_snr = (low_snr + high_snr) / 2
            calculated_rate = self.physics.calculate_max_bitrate(mid_snr, distance_m)

            if calculated_rate >= target_rate_mbps:
                optimal_snr = mid_snr
                high_snr = mid_snr
            else:
                low_snr = mid_snr

        return round(optimal_snr, 1)

    def _prepare_data(self, experiment_results: list) -> tuple:
        """
        Prepares training data from raw experiment results using the advanced physics model.
        """
        features = []
        targets = []

        for result in experiment_results:
            if result["manipulation_success"] and result["measured_speed_mbps"] > 0:
                # Feature: The resulting speed
                features.append([result["measured_speed_mbps"]])

                # Targets: The parameters that would have been set to achieve the target rate
                target_rate = result["target_rate_mbps"]
                target_distance = result["target_distance_m"]

                # Recalculate the parameters using the new physics model
                target_snr = self._find_optimal_snr_for_rate(target_rate, target_distance)
                attenuations = self.physics.model_frequency_dependent_attenuation(target_distance)
                target_attenuation = np.mean(list(attenuations.values()))

                targets.append([target_snr, target_attenuation])

        return np.array(features), np.array(targets)

    def train(self, experiment_results: list):
        """
        Trains the internal regression model on the provided experiment data.
        """
        print("Preparing data and training AI model using advanced physics...")
        X, y = self._prepare_data(experiment_results)

        if len(X) < 2:
            print("Not enough valid data to train the model. Run more experiments.")
            self._is_trained = False
            return

        self.model.fit(X, y)
        self._is_trained = True
        print("AI model training complete.")

    def predict_optimal_params(self, target_rate_mbps: float) -> dict | None:
        """
        Predicts the optimal SNR and attenuation for a given target data rate.
        """
        if not self._is_trained:
            print("Model is not trained yet. Please train the model first.")
            return None

        predicted_params = self.model.predict([[target_rate_mbps]])[0]

        result = {
            "predicted_snr": round(predicted_params[0], 1),
            "predicted_attenuation": round(predicted_params[1], 1),
        }

        print(f"AI prediction for {target_rate_mbps} Mbps -> {result}")
        return result