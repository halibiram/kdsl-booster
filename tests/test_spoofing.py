import pytest
from unittest.mock import MagicMock, patch
from src.spoofing import (
    calculate_realistic_attenuation,
    DynamicSNRSpoofer,
    KernelDSLManipulator,
)

def test_calculate_realistic_attenuation():
    """
    Tests the attenuation calculation with various distances.
    """
    # Test based on the reference value from the project spec
    # 300m -> 18.5 dB
    assert calculate_realistic_attenuation(300) == 18.5

    # Test a shorter distance
    # 100m should be roughly a third of 300m, so ~6.2 dB
    assert calculate_realistic_attenuation(100) == 6.2

    # Test a very short distance
    assert calculate_realistic_attenuation(10) == 0.6

    # Test the edge case of zero or negative distance
    assert calculate_realistic_attenuation(0) == 0.5
    assert calculate_realistic_attenuation(-100) == 0.5


def test_dynamic_snr_spoofer_initialization():
    """
    Tests that the DynamicSNRSpoofer class initializes correctly.
    """
    spoofer = DynamicSNRSpoofer(base_rate_mbps=30, base_snr_db=25)
    assert spoofer.base_rate_mbps == 30
    assert spoofer.base_snr_db == 25
    assert spoofer.LOG2_FACTOR == 6.0


def test_calculate_optimal_snr_curve():
    """
    Tests the SNR calculation for various target data rates.
    """
    spoofer = DynamicSNRSpoofer(base_rate_mbps=30, base_snr_db=25)

    # Test doubling the rate (should add exactly 6 dB)
    # 30 -> 60 Mbps should require 25 + 6 = 31 dB
    assert spoofer.calculate_optimal_snr_curve(target_rate_mbps=60) == 31.0

    # Test quadrupling the rate (should add 12 dB)
    # 30 -> 120 Mbps should require 25 + 12 = 37 dB
    assert spoofer.calculate_optimal_snr_curve(target_rate_mbps=120) == 37.0

    # Test a non-integer rate increase
    # 30 -> 100 Mbps
    # SNR = 25 + 6 * log2(100/30) = 25 + 6 * 1.737 = 25 + 10.42 = 35.4
    assert spoofer.calculate_optimal_snr_curve(target_rate_mbps=100) == 35.4

    # Test a target rate lower than the base rate (should return base SNR)
    assert spoofer.calculate_optimal_snr_curve(target_rate_mbps=20) == 25.0

    # Test a target rate equal to the base rate (should return base SNR)
    assert spoofer.calculate_optimal_snr_curve(target_rate_mbps=30) == 25.0


@pytest.fixture
def mock_manipulator(mocker):
    """Provides a KernelDSLManipulator instance with mocked dependencies."""
    mock_ssh = MagicMock()

    # Mock the constructor of DynamicSNRSpoofer to control its instance
    mock_snr_spoofer_instance = MagicMock()
    mock_snr_spoofer_instance.calculate_optimal_snr_curve.return_value = 35.4
    mocker.patch('src.spoofing.DynamicSNRSpoofer', return_value=mock_snr_spoofer_instance)

    # Mock the standalone functions
    mocker.patch('src.spoofing.calculate_realistic_attenuation', return_value=1.0)
    mock_write_param = mocker.patch('src.spoofing.write_kernel_parameter', return_value=True)

    manipulator = KernelDSLManipulator(
        ssh_interface=mock_ssh,
        base_rate_mbps=30,
        base_snr_db=25,
    )

    return manipulator, mock_snr_spoofer_instance, mock_write_param

def test_set_target_profile_orchestration(mock_manipulator):
    """
    Tests that KernelDSLManipulator correctly orchestrates the spoofing process.
    It should call the calculation models and then write the results to the kernel.
    """
    manipulator, mock_snr_spoofer, mock_write_kernel_parameter = mock_manipulator

    target_rate = 100
    target_distance = 20

    # Execute the main orchestration method
    results = manipulator.set_target_profile(
        target_rate_mbps=target_rate, target_distance_m=target_distance
    )

    # 1. Verify that the calculation models were called correctly
    mock_snr_spoofer.calculate_optimal_snr_curve.assert_called_once_with(target_rate)
    # We can't assert on the standalone function directly, but we know its return value is used.

    # 2. Verify that the kernel parameters were written with the calculated values
    expected_snr_path = manipulator.PARAM_PATHS["snr_margin"]
    expected_attenuation_path = manipulator.PARAM_PATHS["attenuation"]

    # Check that write_kernel_parameter was called for SNR
    mock_write_kernel_parameter.assert_any_call(
        manipulator.ssh_interface, expected_snr_path, "35.4"
    )

    # Check that write_kernel_parameter was called for Attenuation
    mock_write_kernel_parameter.assert_any_call(
        manipulator.ssh_interface, expected_attenuation_path, "1.0"
    )

    # 3. Verify the final results dictionary
    assert results["snr_margin_set"] is True
    assert results["attenuation_set"] is True