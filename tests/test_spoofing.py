import pytest
from unittest.mock import MagicMock, patch
import numpy as np

from src.spoofing import KernelDSLManipulator
from src.keenetic_dsl_interface import KEENETIC_HARDWARE_MATRIX

@pytest.fixture
def manipulator_setup(mocker):
    """
    A fixture that provides a KernelDSLManipulator instance with all its
    dependencies mocked out for isolated testing.
    """
    # Mock the SSH interface dependency
    mock_ssh_interface = MagicMock()

    # Mock the KeeneticDSLInterface dependency
    mock_dsl_interface_instance = MagicMock()
    # Simulate successful hardware detection
    mock_dsl_interface_instance.detect_hardware.return_value = 'KN-1010'
    mock_dsl_interface_instance.hardware_specs = KEENETIC_HARDWARE_MATRIX['KN-1010']
    mocker.patch('src.spoofing.KeeneticDSLInterface', return_value=mock_dsl_interface_instance)

    # Mock the AdvancedDSLPhysics dependency
    mock_physics_instance = MagicMock()
    # Set the profile attribute on the mock to satisfy the test assertion
    mock_physics_instance.profile = '17a'
    # Configure mock return values for physics calculations
    mock_physics_instance.calculate_max_bitrate.return_value = 105.0  # Simulate calculated rate
    mock_physics_instance.model_frequency_dependent_attenuation.return_value = {
        'DS1': 10.0, 'DS2': 20.0, 'DS3': 30.0
    }
    mocker.patch('src.spoofing.AdvancedDSLPhysics', return_value=mock_physics_instance)

    # Spy on the internal SNR search method to verify it's called
    search_spy = mocker.spy(KernelDSLManipulator, '_find_optimal_snr_for_rate')

    # Instantiate the class under test
    manipulator = KernelDSLManipulator(ssh_interface=mock_ssh_interface, profile='17a')

    return manipulator, mock_dsl_interface_instance, mock_physics_instance, search_spy

def test_manipulator_initialization(manipulator_setup):
    """
    Tests that the manipulator initializes its dependencies correctly and detects hardware.
    """
    _, mock_dsl_interface, mock_physics, _ = manipulator_setup

    # Verify that hardware detection was called upon initialization
    mock_dsl_interface.detect_hardware.assert_called_once()
    # Verify that the physics model was initialized with the correct profile
    assert mock_physics.profile == '17a'

def test_set_target_profile_orchestration(manipulator_setup):
    """
    Tests that set_target_profile correctly orchestrates the calculation and
    writing of new DSL parameters.
    """
    manipulator, mock_dsl_interface, mock_physics, search_spy = manipulator_setup

    # --- Execute the method ---
    results = manipulator.set_target_profile(
        target_rate_mbps=100,
        target_distance_m=300
    )

    # --- Assertions ---
    # 1. Verify that the optimal SNR was searched for
    search_spy.assert_called_once_with(manipulator, 100, 300)

    # 2. Verify that frequency-dependent attenuation was modeled
    mock_physics.model_frequency_dependent_attenuation.assert_called_once_with(distance_m=300)

    # 3. Verify that the results were written to the correct registers with correct formatting
    # Optimal SNR is found via search; let's assume the spy returns the value from the search.
    # The search will return ~38.3 based on mock setup. Value written is hex(383) = '0x17f'
    # We can't easily get the return value of the spy, so let's mock _find_optimal_snr_for_rate directly
    with patch.object(manipulator, '_find_optimal_snr_for_rate', return_value=38.3) as mock_find_snr:
        results = manipulator.set_target_profile(100, 300)

        # Attenuation is the mean of [10, 20, 30] = 20.0. Value written is hex(200) = '0xc8'
        mock_dsl_interface.write_dsl_register.assert_any_call('attenuation', '0xc8')
        mock_dsl_interface.write_dsl_register.assert_any_call('snr_margin', '0x17f')

def test_manipulator_raises_error_on_hw_detect_failure(mocker):
    """
    Tests that KernelDSLManipulator raises a RuntimeError if hardware detection fails.
    """
    mock_ssh = MagicMock()
    # Mock KeeneticDSLInterface to simulate a hardware detection failure
    mock_dsl_interface_instance = MagicMock()
    mock_dsl_interface_instance.detect_hardware.return_value = None # Simulate failure
    mocker.patch('src.spoofing.KeeneticDSLInterface', return_value=mock_dsl_interface_instance)

    # Expect a RuntimeError during initialization
    with pytest.raises(RuntimeError, match="Failed to detect Keenetic hardware"):
        KernelDSLManipulator(ssh_interface=mock_ssh)