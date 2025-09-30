import pytest
from unittest.mock import MagicMock
from src.experimentation import ExperimentRunner

@pytest.fixture
def mock_ssh_interface():
    """Provides a mocked EntwareSSHInterface."""
    return MagicMock()

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

def test_experiment_runner_initialization(mock_manipulator, mock_ssh_interface):
    """
    Tests that the ExperimentRunner initializes correctly.
    """
    runner = ExperimentRunner(manipulator=mock_manipulator, ssh_interface=mock_ssh_interface)
    assert runner.manipulator is mock_manipulator
    assert runner.ssh is mock_ssh_interface
    assert runner.results == []

def test_parameter_sweep(mock_manipulator, mock_ssh_interface):
    """
    Tests that the parameter_sweep method correctly iterates through ranges
    and calls the manipulator for each combination.
    """
    runner = ExperimentRunner(manipulator=mock_manipulator, ssh_interface=mock_ssh_interface)

    # Mock the performance measurer to return a deterministic result for the test
    mock_measurer = MagicMock()
    def mock_measure(manipulation_result, target_rate_mbps, method):
        # This mock now returns the method that was passed to it
        return {
            "measured_speed_mbps": target_rate_mbps * 0.95, # deterministic simulation
            "measurement_method": method,
            "success": True,
        }
    mock_measurer.measure_performance.side_effect = mock_measure
    runner.performance_measurer = mock_measurer

    # Define simple ranges for the test
    rate_range = [100, 120]  # 2 rates
    distance_range = [10, 20, 30]  # 3 distances

    # Run the sweep, explicitly passing a measurement method
    runner.parameter_sweep(rate_range, distance_range, measurement_method="mock_test")

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
    assert last_result["measured_speed_mbps"] == 114.0 # 120 * 0.95
    assert last_result["applied_snr_db"] == 35.0
    assert last_result["applied_attenuation_db"] == 15.0
    # Verify that the measurement method was passed through correctly
    assert last_result["measurement_method"] == "mock_test"


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

    # Run a single experiment
    runner.parameter_sweep([100], [10])

    assert len(runner.results) == 1
    result = runner.results[0]
    assert result["manipulation_success"] is False
    # Performance should be 0 if manipulation fails
    assert result["measured_speed_mbps"] == 0.0
    assert result["applied_snr_db"] == 0
    # Verify that the measurement method is correctly reported as 'none'
    assert result["measurement_method"] == "none"