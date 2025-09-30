import numpy as np
import logging
from sklearn.linear_model import Ridge  # Regularized regression
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score

logger = logging.getLogger("dsl_bypass")

class AIOptimizer:
    """
    Enhanced AI optimizer with proper feature engineering and validation
    """
    def __init__(self, regularization_alpha=1.0):
        self.model = Ridge(alpha=regularization_alpha)
        self.scaler_X = StandardScaler()
        self.scaler_y = StandardScaler()
        self._is_trained = False
        self.training_metrics = {}

    def _prepare_data(self, experiment_results: list) -> tuple:
        """
        Enhanced feature engineering with multiple input features
        """
        features = []
        targets = []

        for result in experiment_results:
            if not result.get("manipulation_success"):
                continue

            measured_speed = result.get("measured_speed_mbps", 0)
            if measured_speed <= 0:
                continue

            # ENHANCED FEATURES
            feature_vector = [
                measured_speed,                          # Measured speed
                result.get("target_rate_mbps", 0),      # Target rate
                result.get("target_distance_m", 0),     # Target distance
                result.get("baseline_snr_db", 25),      # Baseline SNR
                result.get("baseline_attenuation_db", 18), # Baseline attenuation
            ]

            # TARGET VARIABLES (what we want to predict)
            target_snr = result.get("applied_snr_db", 0)
            target_attenuation = result.get("applied_attenuation_db", 0)

            if target_snr > 0 and target_attenuation > 0:
                features.append(feature_vector)
                targets.append([target_snr, target_attenuation])

        if len(features) < 5:
            logger.warning(f"Only {len(features)} valid samples for training")

        return np.array(features), np.array(targets)

    def train(self, experiment_results: list, validation_split=0.2):
        """
        Train with proper validation
        """
        logger.info("Preparing data and training AI model...")
        X, y = self._prepare_data(experiment_results)

        if len(X) < 5:
            logger.error("Not enough data to train the model. Need at least 5 samples.")
            return

        # Split data for validation
        if len(X) >= 10:
            X_train, X_val, y_train, y_val = train_test_split(
                X, y, test_size=validation_split, random_state=42
            )
        else:
            X_train, y_train = X, y
            X_val, y_val = None, None

        # Normalize features
        X_train_scaled = self.scaler_X.fit_transform(X_train)
        y_train_scaled = self.scaler_y.fit_transform(y_train)

        # Train model
        self.model.fit(X_train_scaled, y_train_scaled)
        self._is_trained = True

        # Calculate training metrics
        y_train_pred_scaled = self.model.predict(X_train_scaled)
        y_train_pred = self.scaler_y.inverse_transform(y_train_pred_scaled)

        train_mse = mean_squared_error(y_train, y_train_pred)
        train_r2 = r2_score(y_train, y_train_pred)

        self.training_metrics = {
            "train_mse": train_mse,
            "train_r2": train_r2,
            "n_samples": len(X_train)
        }

        logger.info(f"Training complete. MSE: {train_mse:.2f}, R²: {train_r2:.3f}")

        # Validation if enough data
        if X_val is not None:
            X_val_scaled = self.scaler_X.transform(X_val)
            y_val_pred_scaled = self.model.predict(X_val_scaled)
            y_val_pred = self.scaler_y.inverse_transform(y_val_pred_scaled)

            val_mse = mean_squared_error(y_val, y_val_pred)
            val_r2 = r2_score(y_val, y_val_pred)

            self.training_metrics["val_mse"] = val_mse
            self.training_metrics["val_r2"] = val_r2

            logger.info(f"Validation: MSE: {val_mse:.2f}, R²: {val_r2:.3f}")

    def predict_optimal_params(self, target_rate_mbps: float,
                              baseline_snr_db: float = 25,
                              baseline_attenuation_db: float = 18,
                              target_distance_m: float = 50) -> dict:
        """
        Enhanced prediction with confidence intervals
        """
        if not self._is_trained:
            logger.warning("Model is not trained yet.")
            return None

        # Prepare feature vector
        feature_vector = np.array([[
            target_rate_mbps * 0.95,  # Expected measured speed (95% of target)
            target_rate_mbps,
            target_distance_m,
            baseline_snr_db,
            baseline_attenuation_db
        ]])

        # Scale and predict
        feature_scaled = self.scaler_X.transform(feature_vector)
        prediction_scaled = self.model.predict(feature_scaled)
        prediction = self.scaler_y.inverse_transform(prediction_scaled)[0]

        result = {
            "predicted_snr": round(float(prediction[0]), 1),
            "predicted_attenuation": round(float(prediction[1]), 1),
            "confidence": self._calculate_confidence(feature_vector),
            "training_metrics": self.training_metrics
        }

        logger.info(f"AI prediction for {target_rate_mbps} Mbps -> {result}")
        return result

    def _calculate_confidence(self, feature_vector: np.ndarray) -> float:
        """
        Calculate prediction confidence based on training data distribution
        """
        if not hasattr(self.scaler_X, 'mean_'):
            return 0.5

        # Distance from training data centroid (simplified confidence)
        feature_scaled = self.scaler_X.transform(feature_vector)
        distance_from_center = np.linalg.norm(feature_scaled)

        # Confidence decreases with distance from training data
        confidence = max(0.0, min(1.0, 1.0 - (distance_from_center / 10)))

        return round(confidence, 2)