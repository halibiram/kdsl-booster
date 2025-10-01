import pytest
from unittest.mock import MagicMock, patch
from src.spoofing import KernelDSLManipulator
from src.entware_ssh import EntwareSSHInterface
from src.keenetic_dsl_interface import DslHalBase
import numpy as np

@pytest.fixture
def mock_ssh():
    """Fixture for a mocked EntwareSSHInterface."""
    return MagicMock(spec=EntwareSSHInterface)

@pytest.fixture
def mock_hal(mocker):
    """Fixture for a mocked DslHalBase, which is returned by the factory."""
    hal = MagicMock(spec=DslHalBase)
    # Mock the get_hal method of the factory to return our mocked HAL
    mocker.patch('src.keenetic_dsl_interface.KeeneticDSLInterface.get_hal', return_value=hal)
    return hal

@pytest.fixture
def manipulator(mock_ssh, mock_hal):
    """Fixture for a KernelDSLManipulator instance with a mocked HAL."""
    # The mock_hal fixture already patches the factory, so this will use the mock
    return KernelDSLManipulator(ssh_interface=mock_ssh, profile='17a')

def test_set_per_tone_bit_loading(manipulator, mock_hal):
    """Verify that set_per_tone_bit_loading calls the HAL with the correct table."""
    bit_table = {100: 12, 200: 8}
    manipulator.set_per_tone_bit_loading(bit_table)
    mock_hal.set_bitloading_table.assert_called_once_with(bit_table)

def test_set_per_tone_bit_loading_invalid_bits(manipulator, mock_hal):
    """Verify that the bit loading function rejects values outside the 0-15 range."""
    bit_table = {100: 16, 200: 8} # 16 is invalid
    result = manipulator.set_per_tone_bit_loading(bit_table)
    assert not result
    mock_hal.set_bitloading_table.assert_not_called()

def test_control_tone_activation(manipulator, mock_hal):
    """Verify that control_tone_activation calls the HAL with the correct map."""
    manipulator.control_tone_activation(tones_to_disable=[10, 20], tones_to_enable=[30])
    expected_map = {10: False, 20: False, 30: True}
    mock_hal.set_tone_activation.assert_called_once_with(expected_map)

def test_manipulate_subcarrier_spacing(manipulator, mock_hal):
    """Verify that manipulate_subcarrier_spacing calls the HAL with the correct value."""
    spacing = 8.625
    manipulator.manipulate_subcarrier_spacing(spacing)
    mock_hal.set_subcarrier_spacing.assert_called_once_with(spacing)

def test_optimize_tone_allocation(manipulator, mock_hal, mocker):
    """Verify the logic of the tone allocation optimization."""
    # 1. Mock the physics model's output
    # Simulate 4 tones: 2 good, 1 marginal (above SNR gap), 1 bad
    mock_snr_profile = np.array([30.0, 25.0, 14.0, 4.0])
    mock_tone_indices = np.array([100, 101, 102, 103])

    mocker.patch.object(manipulator.physics, 'calculate_snr_per_tone', return_value=mock_snr_profile)
    mocker.patch.object(manipulator.physics, 'get_tone_indices', return_value=mock_tone_indices)

    # 2. Run the optimization
    manipulator.optimize_tone_allocation(target_distance_m=100, snr_threshold_db=6.0)

    # 3. Verify the HAL calls
    # Tones with SNR < 6.0 dB should be disabled. In our mock, tone 103 (4.0 dB).
    mock_hal.set_tone_activation.assert_called_once_with({103: False})

    # The bit-loading table should reflect the calculated bits for each tone.
    # We expect tones 100, 101, 102 to have bits, and 103 to have 0.
    # The exact bit values depend on the Shannon-Hartley calculation in the method.
    # Let's check that the call was made and that the disabled tone has 0 bits.
    mock_hal.set_bitloading_table.assert_called_once()
    final_bit_table = mock_hal.set_bitloading_table.call_args[0][0]

    assert final_bit_table[103] == 0  # Disabled tone must have 0 bits
    assert final_bit_table[100] > 0   # Good tones should have > 0 bits
    assert final_bit_table[101] > 0
    assert final_bit_table[102] > 0   # Marginal but above-threshold tone should have bits

def test_dmt_methods_handle_notimplemented(manipulator, mock_hal):
    """Verify that DMT methods handle NotImplementedError from the HAL gracefully."""
    mock_hal.set_bitloading_table.side_effect = NotImplementedError
    mock_hal.set_tone_activation.side_effect = NotImplementedError
    mock_hal.set_subcarrier_spacing.side_effect = NotImplementedError

    assert not manipulator.set_per_tone_bit_loading({100: 10})
    assert not manipulator.control_tone_activation(tones_to_disable=[10])
    assert not manipulator.manipulate_subcarrier_spacing(4.3125)