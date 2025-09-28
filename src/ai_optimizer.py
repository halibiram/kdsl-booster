"""
This module provides an AI-powered optimizer for DSL parameters.

It uses machine learning models trained on data from the ExperimentRunner
to predict the optimal parameters (e.g., SNR margin, attenuation) required
to achieve a target performance metric, such as data rate.
"""

import numpy as np
from sklearn.linear_model import LinearRegression
from src.spoofing import calculate_realistic_attenuation, DynamicSNRSpoofer


class AIOptimizer:
    """
    Uses a simple machine learning model to predict optimal DSL parameters.
    """

    def __init__(self):
        """
        Initializes the AIOptimizer with a regression model.
        """
        # We are predicting two values (SNR, Attenuation) from one value (Speed).
        # A simple linear regression model is a good starting point.
        self.model = LinearRegression()
        self._is_trained = False

    def _prepare_data(self, experiment_results: list) -> tuple:
        """
        Prepares training data from experiment results.

        Args:
            experiment_results: A list of result dictionaries from ExperimentRunner.

        Returns:
            A tuple containing feature matrix X (measured speeds) and
            target matrix y (the parameters that produced those speeds).
        """
        features = []
        targets = []

        # We need a baseline to recalculate the target SNR from the target rate
        # This assumes the baseline is consistent, a real implementation might need
        # to store the baseline used for each experiment.
        # For simplicity, we'll instantiate a spoofer with a common baseline.
        temp_snr_spoofer = DynamicSNRSpoofer(base_rate_mbps=30, base_snr_db=25)

        for result in experiment_results:
            # Only train on successful manipulations where a speed was measured
            if result["manipulation_success"] and result["measured_speed_mbps"] > 0:
                # Feature: The resulting speed
                features.append([result["measured_speed_mbps"]])

                # Targets: The parameters that achieved this speed
                target_rate = result["target_rate_mbps"]
                target_distance = result["target_distance_m"]

                # Recalculate the parameters that were set
                target_snr = temp_snr_spoofer.calculate_optimal_snr_curve(target_rate)
                target_attenuation = calculate_realistic_attenuation(target_distance)

                targets.append([target_snr, target_attenuation])

        return np.array(features), np.array(targets)

    def train(self, experiment_results: list):
        """
        Trains the machine learning model on the provided experiment data.

        Args:
            experiment_results: A list of result dictionaries from ExperimentRunner.
        """
        print("Preparing data and training AI model...")
        X, y = self._prepare_data(experiment_results)

        if len(X) < 2:
            print("Not enough data to train the model. Run more experiments.")
            return

        self.model.fit(X, y)
        self._is_trained = True
        print("AI model training complete.")

    def predict_optimal_params(self, target_rate_mbps: float) -> dict | None:
        """
        Predicts the optimal SNR and attenuation for a target data rate.

        Args:
            target_rate_mbps: The desired data rate in Mbps.

        Returns:
            A dictionary with the predicted 'snr' and 'attenuation', or None if
            the model is not trained.
        """
        if not self._is_trained:
            print("Model is not trained yet. Please train the model first.")
            return None

        # The model expects a 2D array for prediction
        predicted_params = self.model.predict([[target_rate_mbps]])[0]

        result = {
            "predicted_snr": round(predicted_params[0], 1),
            "predicted_attenuation": round(predicted_params[1], 1),
        }

        print(f"AI prediction for {target_rate_mbps} Mbps -> {result}")
        return result