import pytest
from unittest.mock import MagicMock, patch
import numpy as np

from src.spoofing import KernelDSLManipulator
from src.advanced_dsl_physics import AdvancedDSLPhysics

@pytest.fixture
def manipulator_setup(mocker):
    """
    A fixture that provides a KernelDSLManipulator instance with its
    dependencies mocked out for isolated testing.
    """
    # Mock the SSH interface dependency
    mock_ssh_interface = MagicMock()

    # Mock the HAL (Hardware Abstraction Layer) that get_hal() would return
    mock_hal_instance = MagicMock()
    mock_hal_instance.set_snr_margin.return_value = True

    # Mock the KeeneticDSLInterface factory
    mock_dsl_interface_factory = MagicMock()
    mock_dsl_interface_factory.get_hal.return_value = mock_hal_instance
    mocker.patch('src.spoofing.KeeneticDSLInterface', return_value=mock_dsl_interface_factory)

    # Mock the AdvancedDSLPhysics dependency
    mock_physics_instance = MagicMock()
    # Configure mock return values for physics calculations
    mock_physics_instance.calculate_snr_per_tone.return_value = np.array([30.0, 35.0, 40.0]) # Avg = 35.0
    mock_physics_instance.model_attenuation_per_tone.return_value = np.array([10.0, 15.0, 20.0]) # Avg = 15.0
    mocker.patch('src.spoofing.AdvancedDSLPhysics', return_value=mock_physics_instance)

    # Instantiate the class under test
    manipulator = KernelDSLManipulator(ssh_interface=mock_ssh_interface, profile='17a')

    return manipulator, mock_hal_instance, mock_physics_instance, mock_dsl_interface_factory

def test_manipulator_initialization(manipulator_setup):
    """
    Tests that the manipulator initializes its dependencies correctly and gets a HAL.
    """
    _, _, mock_physics_instance, mock_dsl_interface_factory = manipulator_setup

    # Verify that the factory was asked to create a HAL instance
    mock_dsl_interface_factory.get_hal.assert_called_once()
    # Verify that the physics model was initialized
    assert isinstance(mock_physics_instance, MagicMock)


def test_set_target_profile_orchestration(manipulator_setup):
    """
    Tests that set_target_profile correctly orchestrates the calculation and
    writing of new DSL parameters via the HAL.
    """
    manipulator, mock_hal, mock_physics, _ = manipulator_setup

    # --- Execute the method ---
    results = manipulator.set_target_profile(
        target_rate_mbps=100,
        target_distance_m=300
    )

    # --- Assertions ---
    # 1. Verify that physical parameters were calculated for the given distance
    mock_physics.calculate_snr_per_tone.assert_called_once_with(distance_m=300)
    mock_physics.model_attenuation_per_tone.assert_called_once_with(distance_m=300)

    # 2. Verify that the HAL was called to set the SNR margin
    # The mock physics calculates an average SNR of 35.0.
    # The register value should be int(35.0 * 10) = 350.
    mock_hal.set_snr_margin.assert_called_once_with(350)

    # 3. Verify the results dictionary is correct
    assert results["snr_margin_set"] is True
    assert results["applied_snr_db"] == 35.0
    assert results["applied_attenuation_db"] == 15.0


def test_manipulator_raises_error_on_hal_failure(mocker):
    """
    Tests that KernelDSLManipulator raises a RuntimeError if HAL initialization fails.
    """
    mock_ssh = MagicMock()
    # Mock KeeneticDSLInterface to simulate a HAL failure
    mock_dsl_interface_factory = MagicMock()
    mock_dsl_interface_factory.get_hal.return_value = None # Simulate failure
    mocker.patch('src.spoofing.KeeneticDSLInterface', return_value=mock_dsl_interface_factory)
    mocker.patch('src.spoofing.AdvancedDSLPhysics')

    # Expect a RuntimeError during initialization
    with pytest.raises(RuntimeError, match="Failed to detect Keenetic hardware or initialize HAL"):
        KernelDSLManipulator(ssh_interface=mock_ssh)

def test_exploit_bonding_enables_and_configures(manipulator_setup):
    """
    Tests that exploit_bonding correctly orchestrates enabling and configuring bonding.
    """
    manipulator, _, _, _ = manipulator_setup
    manipulator.bonding_exploiter = MagicMock()

    # --- Execute the method ---
    manipulator.exploit_bonding(
        enable_bonding=True,
        group_id=1,
        mode='ethernet',
        line_ids=[0, 1],
        delay_ms=15
    )

    # --- Assertions ---
    manipulator.bonding_exploiter.control_bonding.assert_called_once_with(True)
    manipulator.bonding_exploiter.configure_bonding.assert_called_once_with(1, 'ethernet', [0, 1])
    manipulator.bonding_exploiter.optimize_packet_reordering.assert_called_once_with(15)
    manipulator.bonding_exploiter.bypass_single_ended_detection.assert_called_once()

def test_exploit_bonding_disables(manipulator_setup):
    """
    Tests that exploit_bonding correctly orchestrates disabling bonding.
    """
    manipulator, _, _, _ = manipulator_setup
    manipulator.bonding_exploiter = MagicMock()

    # --- Execute the method ---
    manipulator.exploit_bonding(
        enable_bonding=False,
        group_id=1,
        mode='ethernet',
        line_ids=[],
        delay_ms=15
    )

    # --- Assertions ---
    manipulator.bonding_exploiter.control_bonding.assert_called_once_with(False)
    manipulator.bonding_exploiter.configure_bonding.assert_not_called()
    manipulator.bonding_exploiter.optimize_packet_reordering.assert_not_called()
    manipulator.bonding_exploiter.bypass_single_ended_detection.assert_not_called()