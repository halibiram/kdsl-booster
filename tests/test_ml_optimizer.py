import pytest
from unittest.mock import MagicMock
from src.ml_optimizer import KeeneticMLOptimizer

@pytest.fixture
def ml_optimizer():
    """Provides a KeeneticMLOptimizer instance for testing."""
    return KeeneticMLOptimizer(dsl_profile='17a')

def test_optimizer_initialization(ml_optimizer):
    """
    Tests that the optimizer initializes correctly with default values.
    """
    assert ml_optimizer.dsl_profile == '17a'
    assert ml_optimizer.tflite_interpreter is None
    assert ml_optimizer._is_trained is False

def test_load_tflite_model_placeholder(ml_optimizer):
    """
    Tests the placeholder logic for loading a TFLite model.
    """
    # In the current placeholder, this should just work and set the trained flag.
    model_path = "dummy/path/to/model.tflite"
    success = ml_optimizer.load_tflite_model(model_path)

    assert success is True
    assert ml_optimizer._is_trained is True

def test_train_on_keenetic_hardware_placeholder(ml_optimizer):
    """
    Tests the placeholder logic for the hardware-in-the-loop training method.
    """
    # Create some dummy experiment results
    dummy_experiments = [{"measured_speed_mbps": 100}] * 10

    # Before training, the model should not be considered trained
    ml_optimizer._is_trained = False

    # The method should run without errors and set the trained flag
    ml_optimizer.train_on_keenetic_hardware(dummy_experiments)
    assert ml_optimizer._is_trained is True

def test_train_with_insufficient_data_placeholder(ml_optimizer, caplog):
    """
    Tests that the training placeholder correctly handles insufficient data.
    """
    # Only 5 experiments is less than the required 10
    insufficient_data = [{"measured_speed_mbps": 100}] * 5
    ml_optimizer.train_on_keenetic_hardware(insufficient_data)

    # The model should not be marked as trained
    assert ml_optimizer._is_trained is False
    # A warning should be logged
    assert "Insufficient data" in caplog.text

def test_predict_optimal_params_not_trained(ml_optimizer):
    """
    Tests that prediction fails if the model has not been loaded or trained.
    """
    # Ensure the model is not trained
    ml_optimizer._is_trained = False

    prediction = ml_optimizer.predict_optimal_params(current_state={'snr_db': 10})

    assert prediction is None

def test_predict_optimal_params_placeholder_logic(ml_optimizer):
    """
    Tests the placeholder prediction logic after the model is "trained".
    """
    # Mark the model as trained
    ml_optimizer._is_trained = True

    # Test case 1: Low SNR should suggest a positive adjustment
    low_snr_state = {'snr_db': 10, 'data_rate_mbps': 50, 'distance_m': 300}
    prediction_low = ml_optimizer.predict_optimal_params(low_snr_state)
    assert prediction_low is not None
    assert prediction_low['predicted_snr_adjustment'] > 0

    # Test case 2: High SNR should suggest a negative adjustment
    high_snr_state = {'snr_db': 25, 'data_rate_mbps': 100, 'distance_m': 100}
    prediction_high = ml_optimizer.predict_optimal_params(high_snr_state)
    assert prediction_high is not None
    assert prediction_high['predicted_snr_adjustment'] < 0