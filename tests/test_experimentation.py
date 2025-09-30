import pytest
from unittest.mock import MagicMock
from src.experimentation import ExperimentRunner

@pytest.fixture
def mock_manipulator():
    """Provides a mocked KernelDSLManipulator for testing the runner."""
    manipulator = MagicMock()
    # Simulate a successful manipulation result with the full data structure
    manipulator.set_target_profile.return_value = {
        "snr_margin_set": True,
        "attenuation_set": "not_supported",
        "applied_snr_db": 35.0,
        "applied_attenuation_db": 15.0,
    }
    return manipulator

@pytest.fixture
def mock_ssh_interface():
    """Provides a mocked SSH interface for testing."""
    return MagicMock()

def test_experiment_runner_initialization(mock_manipulator, mock_ssh_interface):
    """
    Tests that the ExperimentRunner initializes correctly.
    """
    runner = ExperimentRunner(manipulator=mock_manipulator, ssh_interface=mock_ssh_interface)
    assert runner.manipulator is mock_manipulator
    assert runner.results == []

def test_parameter_sweep(mock_manipulator, mock_ssh_interface):
    """
    Tests that the parameter_sweep method correctly iterates through ranges
    and calls the manipulator for each combination.
    """
    runner = ExperimentRunner(manipulator=mock_manipulator, ssh_interface=mock_ssh_interface)

    # Since the real measurement involves randomness, we mock it to be deterministic
    def mock_measure_performance(manipulation_result, target_rate_mbps, method):
        # Simulate the behavior that was likely intended by the original test assertion
        speed = target_rate_mbps * 0.95
        return {
            "measured_speed_mbps": speed,
            "measurement_method": "mocked_simulation",
            "success": True,
        }

    runner.performance_measurer.measure_performance = MagicMock(side_effect=mock_measure_performance)

    # Define simple ranges for the test
    rate_range = [100, 120]  # 2 rates
    distance_range = [10, 20, 30]  # 3 distances

    # Run the sweep
    runner.parameter_sweep(rate_range, distance_range)

    # 1. Verify that the manipulator was called for each combination (2 * 3 = 6 times)
    assert mock_manipulator.set_target_profile.call_count == 6

    # 2. Verify one of the calls to ensure parameters are passed correctly
    mock_manipulator.set_target_profile.assert_any_call(
        target_rate_mbps=120,
        target_distance_m=30
    )

    # 3. Verify that the results are stored correctly
    assert len(runner.results) == 6

    # Check the structure and content of the last result entry
    last_result = runner.results[-1]
    assert last_result["target_rate_mbps"] == 120
    assert last_result["target_distance_m"] == 30
    assert last_result["manipulation_success"] is True
    # The measured speed is now deterministic due to the mock
    assert last_result["measured_speed_mbps"] == 114.0 # 120 * 0.95
    assert last_result["applied_snr_db"] == 35.0
    assert last_result["applied_attenuation_db"] == 15.0

def test_parameter_sweep_with_failed_manipulation(mock_manipulator, mock_ssh_interface):
    """
    Tests that the runner correctly records a failed experiment.
    """
    # Simulate a failed manipulation
    mock_manipulator.set_target_profile.return_value = {
        "snr_margin_set": False,
        "attenuation_set": "not_supported",
        "applied_snr_db": 0,  # SNR is 0 on failure
        "applied_attenuation_db": 15.0, # Attenuation is still calculated
    }

    runner = ExperimentRunner(manipulator=mock_manipulator, ssh_interface=mock_ssh_interface)

    # The real measure_performance method should handle the failed manipulation correctly,
    # so we don't need to mock it for this test.

    # Run a single experiment
    runner.parameter_sweep([100], [10])

    assert len(runner.results) == 1
    result = runner.results[0]
    assert result["manipulation_success"] is False
    # Performance should be 0 if manipulation fails
    assert result["measured_speed_mbps"] == 0.0
    assert result["applied_snr_db"] == 0