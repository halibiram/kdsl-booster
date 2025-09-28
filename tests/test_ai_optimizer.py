import pytest
import numpy as np
from src.ai_optimizer import AIOptimizer

@pytest.fixture
def sample_experiment_results():
    """
    Provides a sample list of experiment results for training the AI model.
    """
    return [
        {
            "target_rate_mbps": 60,
            "target_distance_m": 200,
            "manipulation_success": {"snr_margin_set": True, "attenuation_set": True},
            "measured_speed_mbps": 58.5,
        },
        {
            "target_rate_mbps": 100,
            "target_distance_m": 100,
            "manipulation_success": {"snr_margin_set": True, "attenuation_set": True},
            "measured_speed_mbps": 95.0,
        },
        {
            "target_rate_mbps": 120,
            "target_distance_m": 50,
            "manipulation_success": {"snr_margin_set": True, "attenuation_set": True},
            "measured_speed_mbps": 115.0,
        },
        # Add a failed experiment that should be ignored by the training
        {
            "target_rate_mbps": 150,
            "target_distance_m": 20,
            "manipulation_success": {"snr_margin_set": False, "attenuation_set": True},
            "measured_speed_mbps": 0,
        },
    ]

def test_ai_optimizer_initialization():
    """
    Tests that the AIOptimizer initializes correctly.
    """
    optimizer = AIOptimizer()
    assert optimizer.model is not None
    assert optimizer._is_trained is False

def test_prepare_data(sample_experiment_results):
    """
    Tests the internal data preparation method.
    """
    optimizer = AIOptimizer()
    X, y = optimizer._prepare_data(sample_experiment_results)

    # Should only process the 3 successful results
    assert X.shape == (3, 1)
    assert y.shape == (3, 2)

    # Check if the first feature (speed) and target (SNR, attenuation) are correct
    assert X[0][0] == 58.5
    # Targets for 60Mbps and 200m: SNR=31.0, Attenuation=12.3
    assert np.isclose(y[0][0], 31.0)
    assert np.isclose(y[0][1], 12.3)

def test_train_and_predict(sample_experiment_results):
    """
    Tests the full train-and-predict workflow of the AIOptimizer.
    """
    optimizer = AIOptimizer()

    # 1. Test prediction before training
    assert optimizer.predict_optimal_params(100) is None

    # 2. Train the model
    optimizer.train(sample_experiment_results)
    assert optimizer._is_trained is True

    # 3. Test prediction after training
    target_rate = 110  # A rate between our sample data points
    prediction = optimizer.predict_optimal_params(target_rate)

    assert prediction is not None
    assert "predicted_snr" in prediction
    assert "predicted_attenuation" in prediction

    # The exact values depend on the linear regression model,
    # but they should be floats within a reasonable range.
    assert isinstance(prediction["predicted_snr"], float)
    assert isinstance(prediction["predicted_attenuation"], float)

def test_train_with_insufficient_data():
    """
    Tests that the training does not proceed with insufficient data.
    """
    optimizer = AIOptimizer()

    # Only one data point is not enough to train
    insufficient_data = [
        {
            "target_rate_mbps": 60,
            "target_distance_m": 200,
            "manipulation_success": {"snr_margin_set": True, "attenuation_set": True},
            "measured_speed_mbps": 58.5,
        }
    ]

    optimizer.train(insufficient_data)
    assert optimizer._is_trained is False