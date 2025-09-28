import pytest
from unittest.mock import MagicMock, patch
from src.spoofing import (
    calculate_realistic_attenuation,
    DynamicSNRSpoofer,
    KernelDSLManipulator,
)
from src.keenetic_dsl_interface import KEENETIC_HARDWARE_MATRIX

# These tests for the calculation models are still valid and do not need changes.
def test_calculate_realistic_attenuation():
    assert calculate_realistic_attenuation(300) == 18.5
    assert calculate_realistic_attenuation(100) == 6.2
    assert calculate_realistic_attenuation(0) == 0.5

def test_dynamic_snr_spoofer_initialization():
    spoofer = DynamicSNRSpoofer(base_rate_mbps=30, base_snr_db=25)
    assert spoofer.base_rate_mbps == 30
    assert spoofer.base_snr_db == 25

def test_calculate_optimal_snr_curve():
    spoofer = DynamicSNRSpoofer(base_rate_mbps=30, base_snr_db=25)
    assert spoofer.calculate_optimal_snr_curve(target_rate_mbps=60) == 31.0
    assert spoofer.calculate_optimal_snr_curve(target_rate_mbps=120) == 37.0
    assert spoofer.calculate_optimal_snr_curve(target_rate_mbps=100) == 35.4

# Updated fixture and test for the refactored KernelDSLManipulator
@pytest.fixture
def mock_manipulator_setup(mocker):
    """
    Provides a KernelDSLManipulator instance with a mocked KeeneticDSLInterface.
    This fixture simulates a successful hardware detection.
    """
    mock_ssh = MagicMock()

    # Mock the KeeneticDSLInterface class
    mock_dsl_interface_class = mocker.patch('src.spoofing.KeeneticDSLInterface')

    # Create an instance of the mock interface
    mock_dsl_interface_instance = MagicMock()

    # Configure the mock instance to simulate successful hardware detection
    mock_dsl_interface_instance.detect_hardware.return_value = "KN-1010"
    mock_dsl_interface_instance.hardware_specs = KEENETIC_HARDWARE_MATRIX["KN-1010"]

    # Make the class return our configured instance
    mock_dsl_interface_class.return_value = mock_dsl_interface_instance

    # Mock the DynamicSNRSpoofer to isolate the manipulator logic
    mock_snr_spoofer_instance = MagicMock()
    mock_snr_spoofer_instance.calculate_optimal_snr_curve.return_value = 35.4
    mocker.patch('src.spoofing.DynamicSNRSpoofer', return_value=mock_snr_spoofer_instance)

    # Now, create the manipulator, which will use our mocks
    manipulator = KernelDSLManipulator(
        ssh_interface=mock_ssh,
        base_rate_mbps=30,
        base_snr_db=25,
    )

    # Return the manipulator and the key mock we want to assert on
    return manipulator, mock_dsl_interface_instance

def test_set_target_profile_orchestration_updated(mock_manipulator_setup):
    """
    Tests that KernelDSLManipulator correctly orchestrates the spoofing process
    using the new KeeneticDSLInterface.
    """
    manipulator, mock_dsl_interface = mock_manipulator_setup

    # Execute the main orchestration method
    results = manipulator.set_target_profile(
        target_rate_mbps=100, target_distance_m=20
    )

    # 1. Verify that the hardware-aware write method was called correctly
    # The calculated SNR is 35.4. The register value should be hex(int(35.4 * 10)) = hex(354) = '0x162'
    mock_dsl_interface.write_dsl_register.assert_any_call(
        'snr_margin', '0x162'
    )

    # The calculated attenuation is 1.2 (20 * 0.0617, rounded).
    # The register value should be hex(int(1.2 * 10)) = hex(12) = '0xc'
    # We use mocker.patch to control this calculation for consistent testing.
    with patch('src.spoofing.calculate_realistic_attenuation', return_value=1.2):
        results = manipulator.set_target_profile(
            target_rate_mbps=100, target_distance_m=20
        )
        mock_dsl_interface.write_dsl_register.assert_any_call(
            'attenuation', '0xc'
        )

    # 2. Verify the final results dictionary
    # We need to configure the return value of our mock to test this
    mock_dsl_interface.write_dsl_register.return_value = True
    results = manipulator.set_target_profile(
        target_rate_mbps=100, target_distance_m=20
    )
    assert results["snr_margin_set"] is True
    assert results["attenuation_set"] is True

def test_manipulator_raises_error_on_hw_detect_failure(mocker):
    """
    Tests that KernelDSLManipulator raises a RuntimeError if hardware detection fails.
    """
    mock_ssh = MagicMock()

    # Mock KeeneticDSLInterface to simulate a hardware detection failure
    mock_dsl_interface_class = mocker.patch('src.spoofing.KeeneticDSLInterface')
    mock_dsl_interface_instance = MagicMock()
    mock_dsl_interface_instance.detect_hardware.return_value = None # Simulate failure
    mock_dsl_interface_class.return_value = mock_dsl_interface_instance

    # Expect a RuntimeError during initialization
    with pytest.raises(RuntimeError, match="Failed to detect Keenetic hardware"):
        KernelDSLManipulator(
            ssh_interface=mock_ssh,
            base_rate_mbps=30,
            base_snr_db=25,
        )